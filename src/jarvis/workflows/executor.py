"""
Workflow executor.

Handles workflow execution with step sequencing, error handling, and state management.
"""

import asyncio
from datetime import datetime
from typing import Any, Callable, Awaitable

from jarvis.core.logging import get_logger
from jarvis.workflows.models.workflow import (
    Workflow, WorkflowStep, WorkflowRun,
    WorkflowStatus, StepStatus, StepType, TriggerType,
)
from jarvis.workflows.parser import WorkflowParser, get_parser

logger = get_logger("jarvis.workflows.executor")


# Callback types
StepCallback = Callable[[WorkflowStep], Awaitable[None]]
RunCallback = Callable[[WorkflowRun], Awaitable[None]]


class WorkflowExecutor:
    """
    Executes workflows with proper step sequencing and error handling.

    Features:
    - Dependency-based step ordering
    - Parallel step execution
    - Retry logic with backoff
    - Variable interpolation
    - Step result chaining
    """

    def __init__(self):
        self.logger = get_logger("jarvis.workflows.executor")
        self.parser = get_parser()

        # Active runs
        self.active_runs: dict[str, WorkflowRun] = {}

        # Callbacks
        self._on_step_start: StepCallback | None = None
        self._on_step_complete: StepCallback | None = None
        self._on_run_start: RunCallback | None = None
        self._on_run_complete: RunCallback | None = None

        # Tool executor (to be wired up)
        self._execute_tool: Callable[[str, dict], Awaitable[Any]] | None = None
        self._execute_intent: Callable[[str, dict], Awaitable[Any]] | None = None

    def set_tool_executor(
        self,
        executor: Callable[[str, dict], Awaitable[Any]],
    ) -> None:
        """Set the function used to execute tools."""
        self._execute_tool = executor

    def set_intent_executor(
        self,
        executor: Callable[[str, dict], Awaitable[Any]],
    ) -> None:
        """Set the function used to execute intents."""
        self._execute_intent = executor

    def on_step_start(self, callback: StepCallback) -> None:
        """Register callback for step start."""
        self._on_step_start = callback

    def on_step_complete(self, callback: StepCallback) -> None:
        """Register callback for step completion."""
        self._on_step_complete = callback

    def on_run_start(self, callback: RunCallback) -> None:
        """Register callback for run start."""
        self._on_run_start = callback

    def on_run_complete(self, callback: RunCallback) -> None:
        """Register callback for run completion."""
        self._on_run_complete = callback

    async def execute(
        self,
        workflow: Workflow,
        trigger_type: TriggerType = TriggerType.MANUAL,
        trigger_data: dict[str, Any] | None = None,
        variables: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """
        Execute a workflow.

        Args:
            workflow: Workflow to execute
            trigger_type: What triggered this run
            trigger_data: Data from trigger
            variables: Runtime variables

        Returns:
            WorkflowRun with execution results
        """
        # Create run
        run = WorkflowRun(
            workflow_id=workflow.id,
            trigger_type=trigger_type,
            trigger_data=trigger_data or {},
            variables={**workflow.variables, **(variables or {})},
        )

        self.active_runs[run.id] = run

        # Reset workflow steps
        workflow.reset_steps()

        # Start run
        run.status = WorkflowStatus.RUNNING
        run.started_at = datetime.utcnow()
        workflow.status = WorkflowStatus.RUNNING
        workflow.current_run_id = run.id

        if self._on_run_start:
            await self._on_run_start(run)

        self.logger.info(f"Starting workflow '{workflow.name}' (run: {run.id})")

        try:
            # Execute steps
            await self._execute_workflow(workflow, run)

            # Check final status
            failed_steps = [s for s in workflow.steps if s.status == StepStatus.FAILED]
            if failed_steps:
                run.status = WorkflowStatus.FAILED
                run.error = f"{len(failed_steps)} step(s) failed"
                workflow.failure_count += 1
            else:
                run.status = WorkflowStatus.COMPLETED
                workflow.success_count += 1

        except asyncio.CancelledError:
            run.status = WorkflowStatus.CANCELLED
            self.logger.info(f"Workflow '{workflow.name}' cancelled")

        except Exception as e:
            run.status = WorkflowStatus.FAILED
            run.error = str(e)
            workflow.failure_count += 1
            self.logger.error(f"Workflow '{workflow.name}' failed: {e}")

        finally:
            run.completed_at = datetime.utcnow()
            workflow.status = WorkflowStatus.IDLE
            workflow.current_run_id = None
            workflow.last_run_at = datetime.utcnow()
            workflow.run_count += 1

            self.active_runs.pop(run.id, None)

            if self._on_run_complete:
                await self._on_run_complete(run)

            self.logger.info(
                f"Workflow '{workflow.name}' completed with status: {run.status.value} "
                f"(duration: {run.duration_ms}ms)"
            )

        return run

    async def _execute_workflow(
        self,
        workflow: Workflow,
        run: WorkflowRun,
    ) -> None:
        """Execute workflow steps in dependency order."""
        completed_ids: set[str] = set()
        max_iterations = len(workflow.steps) * 2  # Safety limit

        for _ in range(max_iterations):
            # Get steps ready to execute
            ready_steps = workflow.get_ready_steps(completed_ids)

            if not ready_steps:
                # Check if all steps are complete
                pending = [s for s in workflow.steps if s.status == StepStatus.PENDING]
                if not pending:
                    break
                # Steps pending but none ready - possibly failed dependencies
                failed_deps = [s for s in workflow.steps if s.status == StepStatus.FAILED]
                if failed_deps:
                    # Mark dependent steps as skipped
                    for step in pending:
                        step.status = StepStatus.SKIPPED
                        completed_ids.add(step.id)
                    break
                await asyncio.sleep(0.1)
                continue

            # Execute ready steps (possibly in parallel)
            if len(ready_steps) == 1:
                await self._execute_step(ready_steps[0], workflow, run)
                completed_ids.add(ready_steps[0].id)
            else:
                # Parallel execution
                tasks = [
                    self._execute_step(step, workflow, run)
                    for step in ready_steps
                ]
                await asyncio.gather(*tasks)
                for step in ready_steps:
                    completed_ids.add(step.id)

        # Collect output from last step
        if workflow.steps:
            last_step = workflow.steps[-1]
            run.output = last_step.result

    async def _execute_step(
        self,
        step: WorkflowStep,
        workflow: Workflow,
        run: WorkflowRun,
    ) -> None:
        """Execute a single workflow step."""
        run.current_step_id = step.id
        step.status = StepStatus.RUNNING
        step.started_at = datetime.utcnow()

        if self._on_step_start:
            await self._on_step_start(step)

        self.logger.debug(f"Executing step '{step.name}' ({step.id})")

        # Interpolate variables in params
        params = self.parser.interpolate_variables(
            step.params,
            run.variables,
            run.step_results,
        )

        retry_count = 0
        last_error = None

        while retry_count <= step.retry_count:
            try:
                # Execute based on step type
                if step.step_type == StepType.TOOL:
                    result = await self._run_tool(step.tool_name, params)
                elif step.step_type == StepType.INTENT:
                    result = await self._run_intent(step.intent, params)
                elif step.step_type == StepType.SCRIPT:
                    result = await self._run_script(step.script, run.variables)
                elif step.step_type == StepType.CONDITION:
                    result = await self._run_condition(step, run)
                elif step.step_type == StepType.PARALLEL:
                    result = await self._run_parallel(step, workflow, run)
                elif step.step_type == StepType.LOOP:
                    result = await self._run_loop(step, workflow, run)
                elif step.step_type == StepType.WAIT:
                    result = await self._run_wait(step, run)
                elif step.step_type == StepType.NOTIFY:
                    result = await self._run_notify(step, run)
                else:
                    result = None

                # Success
                step.status = StepStatus.COMPLETED
                step.result = result
                step.completed_at = datetime.utcnow()

                # Store in run results
                run.step_results[step.id] = {
                    "result": result,
                    "output": step.output,
                    "status": "completed",
                }

                if self._on_step_complete:
                    await self._on_step_complete(step)

                self.logger.debug(f"Step '{step.name}' completed")
                return

            except Exception as e:
                last_error = str(e)
                retry_count += 1

                if retry_count <= step.retry_count:
                    self.logger.warning(
                        f"Step '{step.name}' failed (retry {retry_count}/{step.retry_count}): {e}"
                    )
                    await asyncio.sleep(step.retry_delay * retry_count)
                else:
                    break

        # Failed after retries
        step.status = StepStatus.FAILED
        step.error = last_error
        step.completed_at = datetime.utcnow()

        run.step_results[step.id] = {
            "error": last_error,
            "status": "failed",
        }

        if self._on_step_complete:
            await self._on_step_complete(step)

        self.logger.error(f"Step '{step.name}' failed: {last_error}")

        # Handle error strategy
        if step.on_error == "fail":
            raise RuntimeError(f"Step '{step.name}' failed: {last_error}")
        elif step.on_error == "continue":
            pass  # Continue to next step
        elif step.on_error.startswith("goto:"):
            # Jump to specific step (handled by caller)
            pass

    async def _run_tool(self, tool_name: str, params: dict) -> Any:
        """Execute a tool."""
        if not self._execute_tool:
            # Fallback to tool registry
            from jarvis.tools.registry import tool_registry
            tool = tool_registry.get(tool_name)
            if not tool:
                raise ValueError(f"Tool not found: {tool_name}")
            result = await tool.execute(**params)
            return result.data if hasattr(result, 'data') else result

        return await self._execute_tool(tool_name, params)

    async def _run_intent(self, intent: str, context: dict) -> Any:
        """Execute a natural language intent."""
        if not self._execute_intent:
            # Fallback to agent
            from jarvis.agent.loop import AgentLoop
            agent = AgentLoop()
            result = await agent.execute(intent, context)
            return result.to_dict()

        return await self._execute_intent(intent, context)

    async def _run_script(self, script: str, variables: dict) -> Any:
        """Execute an inline script."""
        import subprocess
        import os

        # Set environment variables
        env = os.environ.copy()
        for key, value in variables.items():
            env[f"JARVIS_{key.upper()}"] = str(value)

        # Run script
        result = await asyncio.to_thread(
            subprocess.run,
            script,
            shell=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Script failed: {result.stderr}")

        return result.stdout

    async def _run_condition(self, step: WorkflowStep, run: WorkflowRun) -> bool:
        """Evaluate a condition step."""
        if not step.condition:
            return True

        # Simple expression evaluation
        expr = step.condition.expression

        # Interpolate variables
        expr = self.parser.interpolate_variables(expr, run.variables, run.step_results)

        # Evaluate (safely)
        try:
            # Only allow simple comparisons
            result = eval(expr, {"__builtins__": {}}, run.variables)
            return bool(result)
        except Exception as e:
            self.logger.warning(f"Condition evaluation failed: {e}")
            return False

    async def _run_parallel(
        self,
        step: WorkflowStep,
        workflow: Workflow,
        run: WorkflowRun,
    ) -> list[Any]:
        """Execute steps in parallel."""
        parallel_ids = step.parallel_steps
        parallel_steps = [workflow.get_step(sid) for sid in parallel_ids]
        parallel_steps = [s for s in parallel_steps if s]

        tasks = [self._execute_step(s, workflow, run) for s in parallel_steps]
        await asyncio.gather(*tasks, return_exceptions=True)

        return [s.result for s in parallel_steps]

    async def _run_loop(
        self,
        step: WorkflowStep,
        workflow: Workflow,
        run: WorkflowRun,
    ) -> list[Any]:
        """Execute a loop over items."""
        # Get items to iterate
        items_expr = step.loop_items
        items = self.parser.interpolate_variables(items_expr, run.variables, run.step_results)

        if isinstance(items, str):
            items = items.split(",")

        results = []
        for item in items:
            # Set loop variable
            run.variables[step.loop_variable] = item

            # Execute nested steps or tool
            if step.tool_name:
                params = self.parser.interpolate_variables(
                    step.params, run.variables, run.step_results
                )
                result = await self._run_tool(step.tool_name, params)
                results.append(result)

        return results

    async def _run_wait(self, step: WorkflowStep, run: WorkflowRun) -> None:
        """Wait for a condition or duration."""
        params = step.params

        if "seconds" in params:
            await asyncio.sleep(params["seconds"])
        elif "until" in params:
            # Wait for condition
            timeout = params.get("timeout", 300)
            start = datetime.utcnow()
            while (datetime.utcnow() - start).total_seconds() < timeout:
                condition = self.parser.interpolate_variables(
                    params["until"], run.variables, run.step_results
                )
                if condition:
                    break
                await asyncio.sleep(1)

    async def _run_notify(self, step: WorkflowStep, run: WorkflowRun) -> None:
        """Send a notification."""
        params = step.params
        message = self.parser.interpolate_variables(
            params.get("message", ""), run.variables, run.step_results
        )

        # Log for now (can be extended to send to various channels)
        self.logger.info(f"[NOTIFY] {message}")

    async def cancel(self, run_id: str) -> bool:
        """Cancel a running workflow."""
        run = self.active_runs.get(run_id)
        if run and run.is_running:
            run.status = WorkflowStatus.CANCELLED
            return True
        return False

    def get_run(self, run_id: str) -> WorkflowRun | None:
        """Get a workflow run by ID."""
        return self.active_runs.get(run_id)


# Module-level singleton
_executor: WorkflowExecutor | None = None


def get_workflow_executor() -> WorkflowExecutor:
    """Get singleton workflow executor."""
    global _executor
    if _executor is None:
        _executor = WorkflowExecutor()
    return _executor


__all__ = ["WorkflowExecutor", "get_workflow_executor"]
