"""
Agent API endpoints.

Handles intent execution, task management, and approvals.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from jarvis.agent import AgentLoop, ExecutionResult
from jarvis.api.deps import get_agent_async
from jarvis.core.constants import ApprovalMode, TaskStatus

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════

class ExecuteRequest(BaseModel):
    """Request to execute an intent."""
    intent: str = Field(..., description="Natural language intent")
    context: dict[str, Any] | None = Field(default=None, description="Execution context")
    approval_mode: str = Field(default="confirm", description="Approval mode: auto, confirm, strict, dry_run")

    model_config = {"json_schema_extra": {
        "examples": [{
            "intent": "run npm test",
            "approval_mode": "confirm"
        }]
    }}


class DirectExecuteRequest(BaseModel):
    """Request to execute a tool directly."""
    tool_name: str = Field(..., description="Name of the tool to execute")
    params: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")

    model_config = {"json_schema_extra": {
        "examples": [{
            "tool_name": "run_command",
            "params": {"command": "npm test"}
        }]
    }}


class ExecutionResponse(BaseModel):
    """Response from execution."""
    task_id: str
    status: str
    message: str
    plan: dict | None = None
    step_results: list[dict] = []
    error: str | None = None
    duration_ms: int = 0


class StepResultResponse(BaseModel):
    """Single step result."""
    step_id: str
    tool_name: str
    status: str
    output: Any = None
    error: str | None = None
    duration_ms: int = 0


# ═══════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/execute", response_model=ExecutionResponse)
async def execute_intent(
    request: ExecuteRequest,
    agent: AgentLoop = Depends(get_agent_async),
):
    """
    Execute a natural language intent.

    The agent will:
    1. Parse the intent
    2. Create an execution plan
    3. Execute the plan steps
    4. Return the results

    **Approval Modes:**
    - `auto`: Auto-approve all operations
    - `confirm`: Ask for approval on high-risk operations
    - `strict`: Ask for approval on all operations
    - `dry_run`: Create plan but don't execute
    """
    # Parse approval mode
    try:
        approval_mode = ApprovalMode(request.approval_mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid approval_mode. Must be one of: {[m.value for m in ApprovalMode]}"
        )

    # Execute
    result = await agent.execute(
        intent=request.intent,
        context=request.context,
        approval_mode=approval_mode,
    )

    return ExecutionResponse(
        task_id=result.task_id,
        status=result.status.value,
        message=result.message,
        plan=result.plan.to_dict() if result.plan else None,
        step_results=[r.to_dict() for r in result.step_results],
        error=result.error,
        duration_ms=result.duration_ms,
    )


@router.post("/execute/direct", response_model=StepResultResponse)
async def execute_tool_direct(
    request: DirectExecuteRequest,
    agent: AgentLoop = Depends(get_agent_async),
):
    """
    Execute a tool directly, bypassing the planner.

    Useful for simple, direct tool invocations.
    """
    result = await agent.execute_direct(
        tool_name=request.tool_name,
        params=request.params,
    )

    return StepResultResponse(
        step_id=result.step_id,
        tool_name=result.tool_name,
        status=result.status,
        output=result.output,
        error=result.error,
        duration_ms=result.duration_ms,
    )


@router.post("/plan")
async def create_plan(
    request: ExecuteRequest,
    agent: AgentLoop = Depends(get_agent_async),
):
    """
    Create an execution plan without executing it.

    Equivalent to execute with approval_mode=dry_run.
    """
    result = await agent.execute(
        intent=request.intent,
        context=request.context,
        approval_mode=ApprovalMode.DRY_RUN,
    )

    return {
        "task_id": result.task_id,
        "plan": result.plan.to_dict() if result.plan else None,
        "message": result.message,
    }


__all__ = ["router"]
