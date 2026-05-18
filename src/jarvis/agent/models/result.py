"""
Execution result models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from jarvis.core.constants import TaskStatus
from jarvis.agent.models.plan import Plan


@dataclass
class StepResult:
    """Result of executing a single step."""
    step_id: str
    tool_name: str
    status: str  # "success" | "error"
    output: Any = None
    error: str | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }

    @property
    def is_success(self) -> bool:
        return self.status == "success"


@dataclass
class ExecutionResult:
    """
    Complete result of executing an agent task.
    """
    task_id: str = field(default_factory=lambda: str(uuid4())[:12])
    status: TaskStatus = TaskStatus.COMPLETED
    plan: Plan | None = None
    step_results: list[StepResult] = field(default_factory=list)

    # Summary
    message: str = ""
    error: str | None = None

    # Timing
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "plan": self.plan.to_dict() if self.plan else None,
            "step_results": [r.to_dict() for r in self.step_results],
            "message": self.message,
            "error": self.error,
            "started_at": self.started_at.isoformat() + "Z",
            "completed_at": self.completed_at.isoformat() + "Z" if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }

    @property
    def is_success(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    @property
    def total_steps(self) -> int:
        return len(self.step_results)

    @property
    def successful_steps(self) -> int:
        return sum(1 for r in self.step_results if r.is_success)

    def finalize(self):
        """Finalize the result with timing."""
        self.completed_at = datetime.utcnow()
        self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)

    @classmethod
    def success(
        cls,
        plan: Plan,
        step_results: list[StepResult],
        message: str = "",
        *,
        task_id: str | None = None,
    ) -> "ExecutionResult":
        """Create a successful result."""
        tid = task_id or str(uuid4())[:12]
        result = cls(
            task_id=tid,
            status=TaskStatus.COMPLETED,
            plan=plan,
            step_results=step_results,
            message=message or f"Completed {len(step_results)} steps successfully",
        )
        result.finalize()
        return result

    @classmethod
    def failure(
        cls,
        error: str,
        plan: Plan | None = None,
        step_results: list[StepResult] | None = None,
        *,
        task_id: str | None = None,
    ) -> "ExecutionResult":
        """Create a failed result."""
        tid = task_id or str(uuid4())[:12]
        result = cls(
            task_id=tid,
            status=TaskStatus.FAILED,
            plan=plan,
            step_results=step_results or [],
            error=error,
            message=f"Task failed: {error}",
        )
        result.finalize()
        return result

    @classmethod
    def cancelled(cls, message: str = "Task was cancelled", *, task_id: str | None = None) -> "ExecutionResult":
        """Create a cancelled result."""
        result = cls(
            task_id=task_id or str(uuid4())[:12],
            status=TaskStatus.CANCELLED,
            message=message,
        )
        result.finalize()
        return result


__all__ = ["ExecutionResult", "StepResult"]
