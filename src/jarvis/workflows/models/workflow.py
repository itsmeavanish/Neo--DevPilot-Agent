"""
Workflow models for automation.

Defines workflow structure, steps, triggers, and execution state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable
from uuid import uuid4


class WorkflowStatus(Enum):
    """Workflow execution status."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Individual step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TriggerType(Enum):
    """Types of workflow triggers."""
    MANUAL = "manual"           # Triggered by user/API
    SCHEDULE = "schedule"       # Cron-based schedule
    FILE_WATCH = "file_watch"   # File system changes
    WEBHOOK = "webhook"         # HTTP webhook
    EVENT = "event"             # Internal event
    GIT = "git"                 # Git events (commit, push)


class StepType(Enum):
    """Types of workflow steps."""
    TOOL = "tool"               # Execute a tool
    INTENT = "intent"           # Natural language intent
    CONDITION = "condition"     # Conditional branching
    PARALLEL = "parallel"       # Parallel execution
    LOOP = "loop"               # Loop over items
    WAIT = "wait"               # Wait for condition/time
    APPROVAL = "approval"       # Wait for user approval
    NOTIFY = "notify"           # Send notification
    SCRIPT = "script"           # Run inline script


@dataclass
class StepCondition:
    """Condition for conditional steps."""
    expression: str             # Condition expression
    on_true: str | None = None  # Step ID to jump to if true
    on_false: str | None = None # Step ID to jump to if false

    def to_dict(self) -> dict[str, Any]:
        return {
            "expression": self.expression,
            "on_true": self.on_true,
            "on_false": self.on_false,
        }


@dataclass
class WorkflowStep:
    """
    A single step in a workflow.
    """
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    name: str = "Unnamed Step"
    step_type: StepType = StepType.TOOL

    # Execution details
    tool_name: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    intent: str | None = None           # For INTENT type
    script: str | None = None           # For SCRIPT type

    # Flow control
    condition: StepCondition | None = None
    parallel_steps: list[str] = field(default_factory=list)  # Step IDs for parallel
    loop_items: str | None = None       # Expression for loop items
    loop_variable: str = "item"         # Variable name in loop

    # Dependencies
    depends_on: list[str] = field(default_factory=list)  # Step IDs

    # Error handling
    on_error: str = "fail"              # fail, continue, retry, goto:<step_id>
    retry_count: int = 0
    retry_delay: float = 1.0
    timeout_seconds: int = 300

    # State
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any = None
    error: str | None = None
    output: str | None = None

    # Metadata
    description: str | None = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if isinstance(self.step_type, str):
            self.step_type = StepType(self.step_type)
        if isinstance(self.status, str):
            self.status = StepStatus(self.status)

    @property
    def is_complete(self) -> bool:
        return self.status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED)

    @property
    def is_success(self) -> bool:
        return self.status == StepStatus.COMPLETED

    @property
    def duration_ms(self) -> int | None:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "step_type": self.step_type.value,
            "tool_name": self.tool_name,
            "params": self.params,
            "intent": self.intent,
            "depends_on": self.depends_on,
            "on_error": self.on_error,
            "retry_count": self.retry_count,
            "timeout_seconds": self.timeout_seconds,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "output": self.output,
            "duration_ms": self.duration_ms,
            "description": self.description,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowStep":
        condition = None
        if data.get("condition"):
            condition = StepCondition(**data["condition"])

        return cls(
            id=data.get("id", str(uuid4())[:8]),
            name=data.get("name", "Unnamed Step"),
            step_type=StepType(data.get("step_type", "tool")),
            tool_name=data.get("tool_name"),
            params=data.get("params", {}),
            intent=data.get("intent"),
            script=data.get("script"),
            condition=condition,
            parallel_steps=data.get("parallel_steps", []),
            loop_items=data.get("loop_items"),
            loop_variable=data.get("loop_variable", "item"),
            depends_on=data.get("depends_on", []),
            on_error=data.get("on_error", "fail"),
            retry_count=data.get("retry_count", 0),
            retry_delay=data.get("retry_delay", 1.0),
            timeout_seconds=data.get("timeout_seconds", 300),
            description=data.get("description"),
            tags=data.get("tags", []),
        )


@dataclass
class WorkflowTrigger:
    """
    Trigger configuration for a workflow.
    """
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    trigger_type: TriggerType = TriggerType.MANUAL
    enabled: bool = True

    # Schedule trigger (cron)
    schedule: str | None = None         # Cron expression
    timezone: str = "UTC"

    # File watch trigger
    watch_paths: list[str] = field(default_factory=list)
    watch_patterns: list[str] = field(default_factory=lambda: ["*"])
    watch_events: list[str] = field(default_factory=lambda: ["created", "modified"])

    # Webhook trigger
    webhook_path: str | None = None
    webhook_secret: str | None = None

    # Event trigger
    event_name: str | None = None
    event_filter: dict[str, Any] = field(default_factory=dict)

    # Git trigger
    git_events: list[str] = field(default_factory=lambda: ["push"])
    git_branches: list[str] = field(default_factory=lambda: ["main"])

    # State
    last_triggered: datetime | None = None
    trigger_count: int = 0

    def __post_init__(self):
        if isinstance(self.trigger_type, str):
            self.trigger_type = TriggerType(self.trigger_type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trigger_type": self.trigger_type.value,
            "enabled": self.enabled,
            "schedule": self.schedule,
            "timezone": self.timezone,
            "watch_paths": self.watch_paths,
            "watch_patterns": self.watch_patterns,
            "watch_events": self.watch_events,
            "webhook_path": self.webhook_path,
            "event_name": self.event_name,
            "event_filter": self.event_filter,
            "git_events": self.git_events,
            "git_branches": self.git_branches,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "trigger_count": self.trigger_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowTrigger":
        return cls(
            id=data.get("id", str(uuid4())[:8]),
            trigger_type=TriggerType(data.get("trigger_type", "manual")),
            enabled=data.get("enabled", True),
            schedule=data.get("schedule"),
            timezone=data.get("timezone", "UTC"),
            watch_paths=data.get("watch_paths", []),
            watch_patterns=data.get("watch_patterns", ["*"]),
            watch_events=data.get("watch_events", ["created", "modified"]),
            webhook_path=data.get("webhook_path"),
            webhook_secret=data.get("webhook_secret"),
            event_name=data.get("event_name"),
            event_filter=data.get("event_filter", {}),
            git_events=data.get("git_events", ["push"]),
            git_branches=data.get("git_branches", ["main"]),
        )


@dataclass
class WorkflowRun:
    """
    A single execution run of a workflow.
    """
    id: str = field(default_factory=lambda: str(uuid4())[:12])
    workflow_id: str = ""

    # Status
    status: WorkflowStatus = WorkflowStatus.IDLE
    current_step_id: str | None = None

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Context
    trigger_type: TriggerType = TriggerType.MANUAL
    trigger_data: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)

    # Results
    step_results: dict[str, dict] = field(default_factory=dict)
    error: str | None = None
    output: Any = None

    def __post_init__(self):
        if isinstance(self.status, str):
            self.status = WorkflowStatus(self.status)
        if isinstance(self.trigger_type, str):
            self.trigger_type = TriggerType(self.trigger_type)

    @property
    def duration_ms(self) -> int | None:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return None

    @property
    def is_running(self) -> bool:
        return self.status == WorkflowStatus.RUNNING

    @property
    def is_complete(self) -> bool:
        return self.status in (
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "current_step_id": self.current_step_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "trigger_type": self.trigger_type.value,
            "trigger_data": self.trigger_data,
            "variables": self.variables,
            "step_results": self.step_results,
            "error": self.error,
            "output": self.output,
        }


@dataclass
class Workflow:
    """
    A workflow definition with steps and triggers.
    """
    id: str = field(default_factory=lambda: str(uuid4())[:12])
    name: str = "Unnamed Workflow"
    description: str | None = None

    # Steps
    steps: list[WorkflowStep] = field(default_factory=list)

    # Triggers
    triggers: list[WorkflowTrigger] = field(default_factory=list)

    # Configuration
    enabled: bool = True
    max_concurrent_runs: int = 1
    timeout_seconds: int = 3600        # 1 hour default

    # Variables and context
    variables: dict[str, Any] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    working_directory: str | None = None

    # State
    status: WorkflowStatus = WorkflowStatus.IDLE
    current_run_id: str | None = None
    last_run_at: datetime | None = None
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.status, str):
            self.status = WorkflowStatus(self.status)

    def get_step(self, step_id: str) -> WorkflowStep | None:
        """Get step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def get_step_by_name(self, name: str) -> WorkflowStep | None:
        """Get step by name."""
        for step in self.steps:
            if step.name == name:
                return step
        return None

    def get_entry_steps(self) -> list[WorkflowStep]:
        """Get steps with no dependencies (entry points)."""
        return [s for s in self.steps if not s.depends_on]

    def get_dependent_steps(self, step_id: str) -> list[WorkflowStep]:
        """Get steps that depend on the given step."""
        return [s for s in self.steps if step_id in s.depends_on]

    def get_ready_steps(self, completed_ids: set[str]) -> list[WorkflowStep]:
        """Get steps ready to execute (all dependencies completed)."""
        ready = []
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue
            if all(dep_id in completed_ids for dep_id in step.depends_on):
                ready.append(step)
        return ready

    def validate(self) -> list[str]:
        """Validate workflow definition. Returns list of errors."""
        errors = []

        if not self.name:
            errors.append("Workflow name is required")

        if not self.steps:
            errors.append("Workflow must have at least one step")

        # Check for duplicate step IDs
        step_ids = [s.id for s in self.steps]
        if len(step_ids) != len(set(step_ids)):
            errors.append("Duplicate step IDs found")

        # Check dependencies exist
        for step in self.steps:
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    errors.append(f"Step '{step.id}' depends on non-existent step '{dep_id}'")

        # Check for circular dependencies
        visited = set()
        path = set()

        def has_cycle(step_id: str) -> bool:
            visited.add(step_id)
            path.add(step_id)
            step = self.get_step(step_id)
            if step:
                for dep_id in step.depends_on:
                    if dep_id in path:
                        return True
                    if dep_id not in visited and has_cycle(dep_id):
                        return True
            path.remove(step_id)
            return False

        for step in self.steps:
            if step.id not in visited:
                if has_cycle(step.id):
                    errors.append("Circular dependency detected")
                    break

        return errors

    def reset_steps(self) -> None:
        """Reset all steps to pending state."""
        for step in self.steps:
            step.status = StepStatus.PENDING
            step.started_at = None
            step.completed_at = None
            step.result = None
            step.error = None
            step.output = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "triggers": [t.to_dict() for t in self.triggers],
            "enabled": self.enabled,
            "max_concurrent_runs": self.max_concurrent_runs,
            "timeout_seconds": self.timeout_seconds,
            "variables": self.variables,
            "env": self.env,
            "working_directory": self.working_directory,
            "status": self.status.value,
            "current_run_id": self.current_run_id,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Workflow":
        steps = [WorkflowStep.from_dict(s) for s in data.get("steps", [])]
        triggers = [WorkflowTrigger.from_dict(t) for t in data.get("triggers", [])]

        return cls(
            id=data.get("id", str(uuid4())[:12]),
            name=data.get("name", "Unnamed Workflow"),
            description=data.get("description"),
            steps=steps,
            triggers=triggers,
            enabled=data.get("enabled", True),
            max_concurrent_runs=data.get("max_concurrent_runs", 1),
            timeout_seconds=data.get("timeout_seconds", 3600),
            variables=data.get("variables", {}),
            env=data.get("env", {}),
            working_directory=data.get("working_directory"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


__all__ = [
    "WorkflowStatus",
    "StepStatus",
    "TriggerType",
    "StepType",
    "StepCondition",
    "WorkflowStep",
    "WorkflowTrigger",
    "WorkflowRun",
    "Workflow",
]
