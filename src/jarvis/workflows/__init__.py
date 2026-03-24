"""
Workflow automation for JARVIS.

Enables automated task sequences with triggers, conditions, and orchestration.
"""

from jarvis.workflows.models.workflow import (
    Workflow,
    WorkflowStep,
    WorkflowTrigger,
    WorkflowRun,
    WorkflowStatus,
    StepStatus,
    TriggerType,
    StepType,
)
from jarvis.workflows.parser import (
    WorkflowParser,
    WorkflowParseError,
    parse_workflow,
)
from jarvis.workflows.executor import (
    WorkflowExecutor,
    get_workflow_executor,
)
from jarvis.workflows.triggers import (
    TriggerManager,
    get_trigger_manager,
)
from jarvis.workflows.engine import (
    WorkflowEngine,
    get_workflow_engine,
)

__all__ = [
    # Models
    "Workflow",
    "WorkflowStep",
    "WorkflowTrigger",
    "WorkflowRun",
    "WorkflowStatus",
    "StepStatus",
    "TriggerType",
    "StepType",
    # Parser
    "WorkflowParser",
    "WorkflowParseError",
    "parse_workflow",
    # Executor
    "WorkflowExecutor",
    "get_workflow_executor",
    # Triggers
    "TriggerManager",
    "get_trigger_manager",
    # Engine
    "WorkflowEngine",
    "get_workflow_engine",
]
