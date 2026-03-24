"""
Plan models for agent execution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from jarvis.core.constants import RiskLevel, OnError, StepStatus


@dataclass
class PlanStep:
    """
    A single step in an execution plan.

    Represents a tool invocation with parameters.
    """
    tool_name: str
    params: dict[str, Any]
    description: str = ""

    # Execution control
    risk_level: RiskLevel = RiskLevel.MEDIUM
    on_error: OnError = OnError.ABORT
    timeout: int = 60
    requires_approval: bool = False

    # Status tracking
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str | None = None

    # Identifiers
    step_id: str = field(default_factory=lambda: str(uuid4())[:8])

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "params": self.params,
            "description": self.description,
            "risk_level": self.risk_level.name,
            "on_error": self.on_error.value,
            "timeout": self.timeout,
            "status": self.status.value,
            "requires_approval": self.requires_approval,
        }

    def mark_running(self):
        """Mark step as running."""
        self.status = StepStatus.RUNNING

    def mark_completed(self, result: Any):
        """Mark step as completed."""
        self.status = StepStatus.COMPLETED
        self.result = result

    def mark_failed(self, error: str):
        """Mark step as failed."""
        self.status = StepStatus.FAILED
        self.error = error

    def mark_skipped(self):
        """Mark step as skipped."""
        self.status = StepStatus.SKIPPED


@dataclass
class Plan:
    """
    An execution plan consisting of multiple steps.

    Created by the Planner and executed by the Executor.
    """
    intent: str
    steps: list[PlanStep] = field(default_factory=list)
    reasoning: str = ""

    # Metadata
    plan_id: str = field(default_factory=lambda: str(uuid4())[:12])
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Computed properties
    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)

    @property
    def current_step_index(self) -> int | None:
        """Get index of currently running step."""
        for i, step in enumerate(self.steps):
            if step.status == StepStatus.RUNNING:
                return i
        return None

    @property
    def has_high_risk_steps(self) -> bool:
        """Check if plan contains high-risk steps."""
        return any(s.risk_level >= RiskLevel.HIGH for s in self.steps)

    @property
    def requires_approval(self) -> bool:
        """Check if any step requires approval."""
        return any(s.requires_approval or s.risk_level >= RiskLevel.HIGH for s in self.steps)

    def get_pending_steps(self) -> list[PlanStep]:
        """Get steps that haven't been executed yet."""
        return [s for s in self.steps if s.status == StepStatus.PENDING]

    def get_high_risk_steps(self) -> list[PlanStep]:
        """Get steps that are high risk or higher."""
        return [s for s in self.steps if s.risk_level >= RiskLevel.HIGH]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "plan_id": self.plan_id,
            "intent": self.intent,
            "reasoning": self.reasoning,
            "steps": [s.to_dict() for s in self.steps],
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "has_high_risk_steps": self.has_high_risk_steps,
            "created_at": self.created_at.isoformat() + "Z",
        }

    def add_step(
        self,
        tool_name: str,
        params: dict,
        description: str = "",
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        on_error: OnError = OnError.ABORT,
    ) -> PlanStep:
        """Add a step to the plan."""
        step = PlanStep(
            tool_name=tool_name,
            params=params,
            description=description,
            risk_level=risk_level,
            on_error=on_error,
        )
        self.steps.append(step)
        return step


__all__ = ["Plan", "PlanStep"]
