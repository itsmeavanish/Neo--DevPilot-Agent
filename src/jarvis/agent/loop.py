"""
Agent Loop - The main orchestrator for JARVIS.

Implements the OODA (Observe, Orient, Decide, Act) loop pattern.
"""

import asyncio
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

from jarvis.agent.planner import Planner
from jarvis.agent.executor import Executor
from jarvis.agent.models.plan import Plan, PlanStep
from jarvis.agent.models.result import ExecutionResult, StepResult
from jarvis.tools.registry import ToolRegistry, tool_registry
from jarvis.core.constants import (
    TaskStatus,
    ApprovalMode,
    RiskLevel,
    StepStatus,
)
from jarvis.core.logging import get_logger
from jarvis.core.exceptions import (
    AgentError,
    PlanningError,
    ExecutionError,
)
from jarvis.self_heal.engine import SelfHealEngine, get_self_heal_engine
from jarvis.devices.distributor import TaskDistributor, get_task_distributor
from jarvis.devices.registry import DeviceRegistry, get_device_registry
from jarvis.execution_context import (
    clear_pairing_context,
    set_pairing_context,
    workspace_from_context,
)

logger = get_logger("jarvis.agent.loop")


class AgentLoop:
    """
    Main agent execution loop.

    Coordinates the full workflow:
    1. OBSERVE: Parse intent, gather context
    2. ORIENT: Retrieve relevant memories, assess situation
    3. DECIDE: Create execution plan via LLM
    4. ACT: Execute plan steps, handle errors
    5. LEARN: Update memory with outcomes (TODO: Phase 2)

    Usage:
        agent = AgentLoop()
        result = await agent.execute("run npm test and fix any failures")
    """

    def __init__(
        self,
        planner: Planner | None = None,
        executor: Executor | None = None,
        tool_registry_instance: ToolRegistry | None = None,
        llm_client: Any = None,
        self_heal_engine: SelfHealEngine | None = None,
        task_distributor: TaskDistributor | None = None,
        device_registry: DeviceRegistry | None = None,
    ):
        """
        Initialize the agent loop.

        Args:
            planner: Planner instance (created if not provided)
            executor: Executor instance (created if not provided)
            tool_registry_instance: Tool registry (uses global if not provided)
            llm_client: LLM client for planning
            self_heal_engine: Self-heal engine (uses global if not provided)
            task_distributor: Task distributor (uses global if not provided)
            device_registry: Device registry (uses global if not provided)
        """
        self.tool_registry = tool_registry_instance or tool_registry
        self.planner = planner or Planner()
        self.executor = executor or Executor()
        self.self_heal = self_heal_engine or get_self_heal_engine()
        self.distributor = task_distributor or get_task_distributor()
        self.device_registry = device_registry or get_device_registry()

        # Wire up dependencies
        self.planner.set_tool_registry(self.tool_registry)
        self.executor.set_tool_registry(self.tool_registry)

        if llm_client:
            self.planner.set_llm_client(llm_client)

        self.logger = get_logger("jarvis.agent.loop")

        # Self-heal settings
        self.pre_execution_health_check = True
        self.auto_resolve_before_execute = False

        # Distribution settings
        self.distributed_execution = False  # Enable to use multi-device execution

        # Event callbacks
        self._on_plan_created: Callable | None = None
        self._on_step_started: Callable | None = None
        self._on_step_completed: Callable | None = None
        self._on_approval_required: Callable | None = None
        self._on_health_issue: Callable | None = None

    def set_llm_client(self, client):
        """Set the LLM client for planning."""
        self.planner.set_llm_client(client)

    def on_plan_created(self, callback: Callable[[Plan], None]):
        """Register callback for when plan is created."""
        self._on_plan_created = callback

    def on_step_completed(self, callback: Callable[[PlanStep, StepResult], None]):
        """Register callback for step completion."""
        self._on_step_completed = callback

    def on_approval_required(self, callback: Callable[[Plan, list[PlanStep]], bool]):
        """Register callback for approval requests. Should return True to approve."""
        self._on_approval_required = callback

    def on_health_issue(self, callback: Callable[[Any], None]):
        """Register callback for when health issues are detected."""
        self._on_health_issue = callback

    async def _run_health_check(self, context: dict[str, Any]) -> None:
        """
        Run pre-execution health check.

        Detects issues that might affect execution.
        """
        if not self.pre_execution_health_check:
            return

        try:
            # Set project context if available
            if "cwd" in context:
                self.self_heal.set_project_root(context["cwd"])

            # Run health check
            status = await self.self_heal.check_health()

            if not status.healthy:
                self.logger.warning(
                    f"Pre-execution health check: {status.errors} errors, "
                    f"{status.critical} critical issues"
                )

                # Notify callback
                if self._on_health_issue:
                    try:
                        self._on_health_issue(status)
                    except Exception as e:
                        self.logger.warning(f"Health callback failed: {e}")

                # Auto-resolve if enabled
                if self.auto_resolve_before_execute:
                    self.logger.info("Attempting auto-resolution of health issues")
                    await self.self_heal.auto_resolve()

        except Exception as e:
            self.logger.debug(f"Health check failed (non-blocking): {e}")

    async def execute(
        self,
        intent: str,
        context: dict[str, Any] | None = None,
        approval_mode: ApprovalMode = ApprovalMode.CONFIRM,
    ) -> ExecutionResult:
        """
        Execute an intent through the agent loop.

        Args:
            intent: Natural language intent (e.g., "run tests")
            context: Additional context (cwd, project info, etc.)
            approval_mode: How to handle approval for risky steps

        Returns:
            ExecutionResult with status and outputs
        """
        exec_context_early = context or {}
        task_id = str(exec_context_early.get("task_id") or "")[:12] or str(uuid4())[:12]
        started_at = datetime.utcnow()

        self.logger.info(f"Task {task_id}: Starting execution of '{intent}'")

        pairing_tokens: tuple | None = None
        try:
            # ═══════════════════════════════════════════════
            # PHASE 1: OBSERVE & ORIENT
            # ═══════════════════════════════════════════════

            # Build execution context
            exec_context = context or {}
            exec_context["task_id"] = task_id
            if "cwd" not in exec_context:
                import os
                exec_context["cwd"] = os.getcwd()

            ws = workspace_from_context(exec_context)
            if ws and not exec_context.get("workspace_root"):
                exec_context["workspace_root"] = ws

            pc = exec_context.get("pairing_code")
            if pc:
                caps = exec_context.get("capabilities")
                if isinstance(caps, str):
                    caps = [c.strip() for c in caps.split(",") if c.strip()]
                elif caps is not None and not isinstance(caps, list):
                    caps = None
                elif isinstance(caps, list) and len(caps) == 0:
                    caps = None
                pairing_tokens = set_pairing_context(
                    str(pc).strip().upper(),
                    caps,
                    workspace_from_context(exec_context),
                )

            # ═══════════════════════════════════════════════
            # PRE-EXECUTION: Health Check
            # ═══════════════════════════════════════════════
            await self._run_health_check(exec_context)

            # Phase 2: Retrieve relevant memories
            try:
                from jarvis.memory.service import get_memory_service
                memory_service = get_memory_service()
                memories = await memory_service.find_patterns(intent, limit=5)
                if memories:
                    memory_context = "\n".join(
                        f"- {m.item.content}" for m in memories[:3]
                    )
                    exec_context["relevant_patterns"] = memory_context
                    self.logger.debug(
                        f"Task {task_id}: Injected {len(memories)} memory patterns"
                    )
            except Exception as mem_err:
                self.logger.debug(f"Memory retrieval skipped: {mem_err}")

            # ═══════════════════════════════════════════════
            # PHASE 2: DECIDE - Create Plan
            # ═══════════════════════════════════════════════

            self.logger.info(f"Task {task_id}: Creating plan")
            plan = await self.planner.create_plan(intent, exec_context)

            if not plan.steps:
                return ExecutionResult(
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    plan=plan,
                    message=plan.reasoning or "No steps required",
                )

            # Notify plan created
            if self._on_plan_created:
                try:
                    self._on_plan_created(plan)
                except Exception as e:
                    self.logger.warning(f"Plan callback failed: {e}")

            self.logger.info(f"Task {task_id}: Plan created with {len(plan.steps)} steps")

            # ═══════════════════════════════════════════════
            # PHASE 3: APPROVAL CHECK
            # ═══════════════════════════════════════════════

            if approval_mode == ApprovalMode.DRY_RUN:
                return ExecutionResult(
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    plan=plan,
                    message="Dry run - plan created but not executed",
                )

            # Check for high-risk steps
            if approval_mode in (ApprovalMode.CONFIRM, ApprovalMode.STRICT):
                high_risk_steps = plan.get_high_risk_steps()

                if approval_mode == ApprovalMode.STRICT:
                    high_risk_steps = plan.steps  # All steps need approval

                if high_risk_steps:
                    approved = await self._request_approval(plan, high_risk_steps)
                    if not approved:
                        return ExecutionResult.cancelled("User declined approval", task_id=task_id)

            # ═══════════════════════════════════════════════
            # PHASE 4: ACT - Execute Plan
            # ═══════════════════════════════════════════════

            self.logger.info(f"Task {task_id}: Executing plan")

            # Step callback
            async def on_step_complete(step: PlanStep, result: StepResult):
                if self._on_step_completed:
                    try:
                        self._on_step_completed(step, result)
                    except Exception as e:
                        self.logger.warning(f"Step callback failed: {e}")

            step_results = await self.executor.execute_plan(
                plan,
                context=exec_context,
                on_step_complete=on_step_complete,
            )

            # ═══════════════════════════════════════════════
            # PHASE 5: FINALIZE
            # ═══════════════════════════════════════════════

            # Check overall success
            failed_steps = [r for r in step_results if not r.is_success]

            if failed_steps:
                error_msgs = [f"{r.tool_name}: {r.error}" for r in failed_steps]
                return ExecutionResult.failure(
                    error="; ".join(error_msgs),
                    plan=plan,
                    step_results=step_results,
                    task_id=task_id,
                )

            # Phase 2: Store successful pattern in memory
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
                    project_id=exec_context.get("project_id"),
                )
                self.logger.debug(f"Task {task_id}: Stored execution pattern in memory")
            except Exception as mem_err:
                self.logger.debug(f"Memory storage skipped: {mem_err}")

            return ExecutionResult.success(
                plan=plan,
                step_results=step_results,
                message=f"Completed {len(step_results)} steps successfully",
                task_id=task_id,
            )

        except PlanningError as e:
            self.logger.error(f"Task {task_id}: Planning failed - {e}")
            return ExecutionResult.failure(f"Planning failed: {e}", task_id=task_id)

        except ExecutionError as e:
            self.logger.error(f"Task {task_id}: Execution failed - {e}")
            return ExecutionResult.failure(f"Execution failed: {e}", task_id=task_id)

        except Exception as e:
            self.logger.exception(f"Task {task_id}: Unexpected error")
            return ExecutionResult.failure(f"Unexpected error: {e}", task_id=task_id)
        finally:
            if pairing_tokens is not None:
                clear_pairing_context(pairing_tokens)

    async def _request_approval(self, plan: Plan, steps: list[PlanStep]) -> bool:
        """
        Request user approval for high-risk steps.

        Returns True if approved, False otherwise.
        """
        if self._on_approval_required:
            try:
                return self._on_approval_required(plan, steps)
            except Exception as e:
                self.logger.warning(f"Approval callback failed: {e}")
                return False

        # No callback registered, auto-approve
        # In production, this should probably default to False
        self.logger.warning("No approval callback registered, auto-approving")
        return True

    async def execute_direct(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> StepResult:
        """
        Execute a single tool directly, bypassing planning.

        Useful for direct tool invocation from API.
        """
        step = PlanStep(
            tool_name=tool_name,
            params=params,
            description=f"Direct execution of {tool_name}",
        )

        return await self.executor.execute_step(step)

    async def get_health_status(self) -> dict:
        """
        Get current health status.

        Returns summary of any detected issues.
        """
        status = await self.self_heal.check_health()
        return status.to_dict()

    async def resolve_health_issues(self, approved: bool = False) -> list[dict]:
        """
        Attempt to resolve any active health issues.

        Args:
            approved: Whether resolutions are pre-approved

        Returns:
            List of resolution records
        """
        async def approval_callback(issue, action):
            return approved

        resolutions = await self.self_heal.auto_resolve(
            approval_callback=approval_callback if approved else None
        )
        return [r.to_dict() for r in resolutions]

    # ═══════════════════════════════════════════════════════════════
    # Distributed Execution
    # ═══════════════════════════════════════════════════════════════

    async def execute_distributed(
        self,
        tool_name: str,
        params: dict[str, Any],
        target_device: str | None = None,
        priority: int = 5,
    ) -> dict:
        """
        Execute a tool on a remote device.

        Args:
            tool_name: Name of tool to execute
            params: Tool parameters
            target_device: Specific device ID (optional)
            priority: Task priority (1-10)

        Returns:
            Distribution result dictionary
        """
        result = await self.distributor.distribute(
            tool_name=tool_name,
            params=params,
            target_device=target_device,
            priority=priority,
        )
        return result.to_dict()

    async def execute_parallel(
        self,
        tasks: list[tuple[str, dict[str, Any]]],
    ) -> list[dict]:
        """
        Execute multiple tools in parallel across devices.

        Args:
            tasks: List of (tool_name, params) tuples

        Returns:
            List of distribution results
        """
        results = await self.distributor.distribute_parallel(tasks)
        return [r.to_dict() for r in results]

    def get_available_devices(self) -> list[dict]:
        """
        Get list of available devices for task execution.

        Returns:
            List of device info dictionaries
        """
        devices = self.device_registry.get_available()
        return [d.to_dict() for d in devices]

    def get_device_status(self, device_id: str) -> dict | None:
        """
        Get status of a specific device.

        Args:
            device_id: Device ID

        Returns:
            Device info dictionary or None
        """
        device = self.device_registry.get(device_id)
        return device.to_dict() if device else None


# Convenience function
async def run_agent(
    intent: str,
    context: dict | None = None,
    llm_client: Any = None,
) -> ExecutionResult:
    """
    Convenience function to run the agent loop.

    Usage:
        result = await run_agent("git status")
    """
    from jarvis.tools.registry import load_builtin_tools
    load_builtin_tools()

    agent = AgentLoop(llm_client=llm_client)
    return await agent.execute(intent, context)


__all__ = ["AgentLoop", "run_agent"]
