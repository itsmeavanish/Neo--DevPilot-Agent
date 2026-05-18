"""
Autonomous execution, deferred human approval, mission telemetry.

- POST /autonomous/execute — plan + optional defer until POST …/approve
- POST /autonomous/runs/{task_id}/approve — approve or reject a deferred run
- GET /autonomous/runs/{task_id} — poll pending run metadata
"""

from __future__ import annotations

import time
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from jarvis.agent import AgentLoop
from jarvis.agent.models.plan import Plan
from jarvis.agent.models.result import ExecutionResult, StepResult
from jarvis.api.deps import get_agent_async
from jarvis.autonomous.classifier import classify_specialist, enhance_intent_for_specialist
from jarvis.autonomous.run_store import PendingAutonomousRun, get_pending, pop_pending, put_pending
from jarvis.core.constants import ApprovalMode, TaskStatus
from jarvis.devices.agent_registry import get_agent_registry
from jarvis.execution_context import (
    clear_pairing_context,
    set_pairing_context,
    workspace_from_context,
)
from jarvis.security.audit import audit_log
from jarvis.security.session_token import mint_session_token, verify_session_token

router = APIRouter(prefix="/autonomous", tags=["Autonomous"])
mission_router = APIRouter(prefix="/mission", tags=["Mission Control"])


def _result_dict(result: ExecutionResult, specialist: str) -> dict[str, Any]:
    return {
        "task_id": result.task_id,
        "status": result.status.value,
        "message": result.message,
        "plan": result.plan.to_dict() if result.plan else None,
        "step_results": [r.to_dict() for r in result.step_results],
        "error": result.error,
        "duration_ms": result.duration_ms,
        "specialist": specialist,
    }


async def _run_health_and_memory_preface(agent: AgentLoop, intent: str, ctx: dict[str, Any]) -> None:
    await agent._run_health_check(ctx)
    try:
        from jarvis.memory.service import get_memory_service

        memory_service = get_memory_service()
        memories = await memory_service.find_patterns(intent, limit=5)
        if memories:
            ctx["relevant_patterns"] = "\n".join(f"- {m.item.content}" for m in memories[:3])
    except Exception:
        pass


async def _execute_only_plan(
    agent: AgentLoop,
    plan: Plan,
    intent: str,
    ctx: dict[str, Any],
    task_id: str,
) -> ExecutionResult:
    """Run an already-approved plan (used after deferred approval)."""
    pairing_tokens: tuple | None = None
    try:
        pc = ctx.get("pairing_code")
        if pc:
            caps = ctx.get("capabilities")
            if isinstance(caps, str):
                caps = [c.strip() for c in caps.split(",") if c.strip()]
            elif caps is not None and not isinstance(caps, list):
                caps = None
            elif isinstance(caps, list) and len(caps) == 0:
                caps = None
            pairing_tokens = set_pairing_context(
                str(pc).strip().upper(),
                caps,
                workspace_from_context(ctx),
            )

        async def on_step_complete(step, result):
            if agent._on_step_completed:
                try:
                    agent._on_step_completed(step, result)
                except Exception:
                    pass

        step_results = await agent.executor.execute_plan(
            plan,
            context=ctx,
            on_step_complete=on_step_complete,
        )

        failed_steps = [r for r in step_results if not r.is_success]
        if failed_steps:
            error_msgs = [f"{r.tool_name}: {r.error}" for r in failed_steps]
            return ExecutionResult.failure(
                "; ".join(error_msgs),
                plan=plan,
                step_results=step_results,
                task_id=task_id,
            )

        try:
            from jarvis.memory.service import get_memory_service

            memory_service = get_memory_service()
            steps_data = [
                {"tool": r.tool_name, "output_preview": str(r.output)[:100]}
                for r in step_results
            ]
            await memory_service.remember_pattern(
                description=intent,
                steps=steps_data,
                project_id=ctx.get("project_id"),
            )
        except Exception:
            pass

        return ExecutionResult.success(
            plan=plan,
            step_results=step_results,
            message=f"Completed {len(step_results)} steps successfully",
            task_id=task_id,
        )
    finally:
        if pairing_tokens is not None:
            clear_pairing_context(pairing_tokens)


class AutonomousExecuteRequest(BaseModel):
    intent: str = Field(..., min_length=1, max_length=4000)
    pairing_code: str = Field(..., min_length=4, max_length=32)
    workspace_root: Optional[str] = Field(
        default=None,
        description="Project folder on the paired laptop; agent file tools stay inside this path.",
    )
    approval_mode: str = Field(default="confirm")
    defer_approval: bool = Field(
        default=True,
        description="If true with confirm/strict, return awaiting_approval until POST …/approve",
    )
    use_multi_agent: bool = Field(default=True)
    specialist: Optional[str] = Field(default=None)
    context: dict[str, Any] | None = None
    capabilities: list[str] | None = None


class ApproveRunRequest(BaseModel):
    approved: bool
    pairing_code: str = Field(..., min_length=4, max_length=32)


class SessionRequest(BaseModel):
    pairing_code: str
    ttl_seconds: int = Field(default=3600, ge=300, le=86400)


@router.post("/execute")
async def autonomous_execute(
    body: AutonomousExecuteRequest,
    agent: AgentLoop = Depends(get_agent_async),
):
    specialist = classify_specialist(body.intent)
    try:
        approval = ApprovalMode(body.approval_mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid approval_mode. Use one of: {[m.value for m in ApprovalMode]}",
        )

    code = body.pairing_code.strip().upper()
    reg = get_agent_registry()
    if not reg.get_agent(code):
        raise HTTPException(
            status_code=503,
            detail="Agent offline — start the laptop agent and keep pairing code active.",
        )

    intent = body.intent.strip()
    if body.use_multi_agent:
        sp = (body.specialist or specialist).lower()
        if sp not in ("debug", "devops", "review", "git", "orchestrator"):
            sp = "orchestrator"
        intent = enhance_intent_for_specialist(body.intent.strip(), sp)

    task_id = str(uuid4())[:12]
    ctx: dict[str, Any] = dict(body.context or {})
    ctx["pairing_code"] = code
    ctx["task_id"] = task_id
    if body.workspace_root and str(body.workspace_root).strip():
        ctx["workspace_root"] = str(body.workspace_root).strip()
    if body.capabilities:
        ctx["capabilities"] = body.capabilities

    audit_log("autonomous_execute", pairing_code=code, detail={"intent_preview": intent[:200]}, success=None)

    defer = body.defer_approval and approval in (ApprovalMode.CONFIRM, ApprovalMode.STRICT)

    if defer:
        await _run_health_and_memory_preface(agent, intent, ctx)
        plan = await agent.planner.create_plan(intent, ctx)

        if not plan.steps:
            result = ExecutionResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                plan=plan,
                message=plan.reasoning or "No steps required",
            )
            result.finalize()
            audit_log("autonomous_complete", pairing_code=code, detail={"task_id": task_id, "status": "completed"}, success=True)
            return _result_dict(result, specialist)

        high_risk = plan.get_high_risk_steps()
        if approval == ApprovalMode.STRICT:
            high_risk = list(plan.steps)

        if high_risk:
            await put_pending(
                PendingAutonomousRun(
                    task_id=task_id,
                    plan=plan,
                    intent=intent,
                    exec_context=dict(ctx),
                    approval_mode=approval,
                    pairing_code=code,
                    created_at=time.time(),
                )
            )
            audit_log(
                "autonomous_awaiting_approval",
                pairing_code=code,
                detail={"task_id": task_id, "risky_steps": len(high_risk)},
                success=None,
            )
            return {
                "task_id": task_id,
                "status": TaskStatus.AWAITING_APPROVAL.value,
                "message": "Review the plan on your phone, then approve or reject.",
                "plan": plan.to_dict(),
                "approval_required": True,
                "steps_for_approval": [s.to_dict() for s in high_risk],
                "step_results": [],
                "error": None,
                "duration_ms": 0,
                "specialist": specialist,
            }

        result = await _execute_only_plan(agent, plan, intent, ctx, task_id)
        audit_log(
            "autonomous_complete",
            pairing_code=code,
            detail={"task_id": task_id, "status": result.status.value},
            success=result.status == TaskStatus.COMPLETED,
        )
        return _result_dict(result, specialist)

    result = await agent.execute(intent=intent, context=ctx, approval_mode=approval)
    audit_log(
        "autonomous_complete",
        pairing_code=code,
        detail={"task_id": result.task_id, "status": result.status.value},
        success=result.status == TaskStatus.COMPLETED,
    )
    return _result_dict(result, specialist)


@router.get("/runs/{task_id}")
async def get_run_status(task_id: str):
    p = await get_pending(task_id)
    if not p:
        raise HTTPException(status_code=404, detail="No pending run with this id (or it expired).")
    return {
        "task_id": p.task_id,
        "status": "awaiting_approval",
        "pairing_code": p.pairing_code,
        "intent_preview": p.intent[:200],
        "plan": p.plan.to_dict(),
        "expires_in_seconds": int(max(0, 3600 - (time.time() - p.created_at))),
    }


@router.post("/runs/{task_id}/approve")
async def approve_run(
    task_id: str,
    body: ApproveRunRequest,
    agent: AgentLoop = Depends(get_agent_async),
):
    """Approve or reject a deferred autonomous run."""
    pending = await pop_pending(task_id)
    if not pending:
        raise HTTPException(status_code=404, detail="Unknown or expired run id.")

    code = body.pairing_code.strip().upper()
    if code != pending.pairing_code:
        raise HTTPException(status_code=403, detail="Pairing code does not match this run.")
    specialist = classify_specialist(pending.intent)

    if not body.approved:
        audit_log("autonomous_rejected", pairing_code=code, detail={"task_id": task_id}, success=False)
        result = ExecutionResult.cancelled("User rejected the plan on device", task_id=task_id)
        return _result_dict(result, specialist)

    audit_log("autonomous_approved", pairing_code=code, detail={"task_id": task_id}, success=True)
    result = await _execute_only_plan(
        agent,
        pending.plan,
        pending.intent,
        pending.exec_context,
        task_id,
    )
    audit_log(
        "autonomous_complete",
        pairing_code=code,
        detail={"task_id": task_id, "status": result.status.value},
        success=result.status == TaskStatus.COMPLETED,
    )
    return _result_dict(result, specialist)


@router.post("/session")
async def create_session(body: SessionRequest):
    code = body.pairing_code.strip().upper()
    if not get_agent_registry().get_agent(code):
        raise HTTPException(status_code=503, detail="Agent not connected; cannot mint session.")
    token = mint_session_token(code, ttl_seconds=body.ttl_seconds)
    audit_log("session_minted", pairing_code=code, detail={"ttl": body.ttl_seconds}, success=True)
    return {"token": token, "expires_in_seconds": body.ttl_seconds, "pairing_code": code}


class VerifySessionRequest(BaseModel):
    token: str


@router.post("/session/verify")
async def verify_session(body: VerifySessionRequest):
    payload = verify_session_token(body.token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"valid": True, "pairing_code": payload["pairing_code"]}


def _predictive_hints(telemetry: dict[str, Any] | None) -> list[str]:
    if not telemetry:
        return []
    hints: list[str] = []
    try:
        cpu = float(telemetry.get("cpu_percent") or 0)
        if cpu > 85:
            hints.append("CPU is very high — consider inspecting top processes or stopping runaway jobs.")
        mem = float(telemetry.get("memory_percent") or 0)
        if mem > 88:
            hints.append("Memory pressure is high — close heavy apps or restart long-running services.")
        disk = float(telemetry.get("disk_percent") or 0)
        if disk > 90:
            hints.append("Disk almost full — archive logs or clean temp folders.")
    except (TypeError, ValueError):
        pass
    return hints


@mission_router.get("/device/{pairing_code}")
async def mission_device(pairing_code: str):
    code = pairing_code.strip().upper()
    reg = get_agent_registry()
    ag = reg.get_agent(code)
    online = ag is not None and getattr(ag, "status", "online") == "online"

    telemetry: dict[str, Any] | None = None
    if online:
        raw = await reg.send_agent_request(
            code,
            {"type": "telemetry_request"},
            wait_timeout=25,
        )
        if raw.get("success"):
            t = raw.get("telemetry")
            if isinstance(t, dict):
                telemetry = t

    return {
        "pairing_code": code,
        "online": online,
        "hostname": ag.hostname if ag else None,
        "platform": ag.platform if ag else None,
        "telemetry": telemetry,
        "predictive_hints": _predictive_hints(telemetry),
    }


__all__ = ["router", "mission_router"]
