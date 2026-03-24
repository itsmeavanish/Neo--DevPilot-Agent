"""
Executor module for JARVIS.

Executes plan steps safely using registered tools.
"""

import asyncio
import time
from typing import Any

from jarvis.agent.models.plan import Plan, PlanStep
from jarvis.agent.models.result import StepResult
from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import ToolRegistry
from jarvis.core.constants import RiskLevel, OnError, StepStatus, MAX_RETRY_ATTEMPTS
from jarvis.core.logging import get_logger
from jarvis.core.exceptions import (
    ToolNotFoundError,
    ToolExecutionError,
    ToolTimeoutError,
    ToolValidationError,
)

logger = get_logger("jarvis.agent.executor")


class Executor:
    """
    Executes plan steps using registered tools.

    Features:
    - Parameter validation
    - Timeout handling
    - Error recovery (retry, continue, abort)
    - Result collection
    """

    def __init__(self, tool_registry: ToolRegistry | None = None):
        """
        Initialize the executor.

        Args:
            tool_registry: Registry of available tools
        """
        self.tool_registry = tool_registry
        self.logger = get_logger("jarvis.agent.executor")

    def set_tool_registry(self, registry: ToolRegistry):
        """Set the tool registry."""
        self.tool_registry = registry

    async def execute_step(
        self,
        step: PlanStep,
        context: dict[str, Any] | None = None,
    ) -> StepResult:
        """
        Execute a single plan step.

        Args:
            step: The step to execute
            context: Execution context (working dir, env vars, etc.)

        Returns:
            StepResult with the outcome
        """
        if not self.tool_registry:
            raise ToolExecutionError(step.tool_name, "Tool registry not configured")

        start_time = time.time()
        step.mark_running()

        try:
            # Get tool
            if not self.tool_registry.has(step.tool_name):
                raise ToolNotFoundError(step.tool_name)

            tool = self.tool_registry.get(step.tool_name)

            # Validate parameters
            errors = tool.validate_params(step.params)
            if errors:
                raise ToolValidationError(step.tool_name, errors)

            # Execute with timeout
            self.logger.info(f"Executing step: {step.tool_name} - {step.description}")

            result = await asyncio.wait_for(
                tool.execute(step.params),
                timeout=step.timeout,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            if result.is_success:
                step.mark_completed(result.output)
                return StepResult(
                    step_id=step.step_id,
                    tool_name=step.tool_name,
                    status="success",
                    output=result.output,
                    duration_ms=duration_ms,
                )
            else:
                step.mark_failed(result.error or "Unknown error")
                return StepResult(
                    step_id=step.step_id,
                    tool_name=step.tool_name,
                    status="error",
                    error=result.error,
                    output=result.output,
                    duration_ms=duration_ms,
                )

        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            error = f"Step timed out after {step.timeout}s"
            step.mark_failed(error)
            self.logger.warning(f"Step timeout: {step.tool_name}")
            return StepResult(
                step_id=step.step_id,
                tool_name=step.tool_name,
                status="error",
                error=error,
                duration_ms=duration_ms,
            )

        except ToolNotFoundError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            step.mark_failed(str(e))
            return StepResult(
                step_id=step.step_id,
                tool_name=step.tool_name,
                status="error",
                error=str(e),
                duration_ms=duration_ms,
            )

        except ToolValidationError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            step.mark_failed(str(e))
            return StepResult(
                step_id=step.step_id,
                tool_name=step.tool_name,
                status="error",
                error=str(e),
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error = f"Unexpected error: {e}"
            step.mark_failed(error)
            self.logger.exception(f"Step execution failed: {e}")
            return StepResult(
                step_id=step.step_id,
                tool_name=step.tool_name,
                status="error",
                error=error,
                duration_ms=duration_ms,
            )

    async def execute_step_with_retry(
        self,
        step: PlanStep,
        max_attempts: int = MAX_RETRY_ATTEMPTS,
        context: dict[str, Any] | None = None,
    ) -> StepResult:
        """
        Execute a step with automatic retry on failure.

        Uses exponential backoff between retries.
        """
        last_result = None

        for attempt in range(max_attempts):
            if attempt > 0:
                # Exponential backoff
                delay = 2 ** attempt
                self.logger.info(f"Retrying step {step.tool_name} (attempt {attempt + 1}/{max_attempts})")
                await asyncio.sleep(delay)

            # Reset step status for retry
            step.status = StepStatus.PENDING
            step.error = None

            result = await self.execute_step(step, context)
            last_result = result

            if result.is_success:
                return result

        # All attempts failed
        return last_result

    async def execute_plan(
        self,
        plan: Plan,
        context: dict[str, Any] | None = None,
        on_step_complete: Any = None,  # Callback: (step, result) -> None
    ) -> list[StepResult]:
        """
        Execute all steps in a plan.

        Args:
            plan: The plan to execute
            context: Execution context
            on_step_complete: Optional callback for each completed step

        Returns:
            List of StepResults
        """
        results = []

        for i, step in enumerate(plan.steps):
            self.logger.info(f"Executing step {i + 1}/{len(plan.steps)}: {step.description}")

            # Handle retry strategy
            if step.on_error == OnError.RETRY:
                result = await self.execute_step_with_retry(step, context=context)
            else:
                result = await self.execute_step(step, context)

            results.append(result)

            # Callback
            if on_step_complete:
                try:
                    await on_step_complete(step, result)
                except Exception as e:
                    self.logger.warning(f"Step callback failed: {e}")

            # Handle error based on on_error strategy
            if not result.is_success:
                if step.on_error == OnError.ABORT:
                    self.logger.warning(f"Aborting plan due to step failure: {step.tool_name}")
                    break
                elif step.on_error == OnError.CONTINUE:
                    self.logger.info(f"Continuing despite step failure: {step.tool_name}")
                    continue
                elif step.on_error == OnError.RETRY:
                    # Already handled above, if still failed, abort
                    self.logger.warning(f"Step failed after retries, aborting: {step.tool_name}")
                    break
                elif step.on_error == OnError.SELF_HEAL:
                    # TODO: Implement self-healing
                    self.logger.warning(f"Self-heal not implemented, aborting: {step.tool_name}")
                    break

        return results


__all__ = ["Executor"]
