"""
Tests for the workflow engine.
"""

import pytest
from pathlib import Path


class TestWorkflowImports:
    """Test workflow module imports."""

    def test_import_models(self):
        from jarvis.workflows.models.workflow import (
            StepType,
            TriggerType,
            WorkflowStep,
            WorkflowTrigger,
            Workflow,
            WorkflowStatus,
        )
        assert StepType is not None
        assert Workflow is not None

    def test_import_parser(self):
        from jarvis.workflows.parser import WorkflowParser
        assert WorkflowParser is not None

    def test_import_executor(self):
        from jarvis.workflows.executor import WorkflowExecutor
        assert WorkflowExecutor is not None

    def test_import_triggers(self):
        from jarvis.workflows.triggers import (
            BaseTrigger,
            ScheduleTrigger,
            FileWatchTrigger,
            TriggerManager,
        )
        assert BaseTrigger is not None
        assert ScheduleTrigger is not None

    def test_import_engine(self):
        from jarvis.workflows.engine import WorkflowEngine
        assert WorkflowEngine is not None


class TestWorkflowModels:
    """Test workflow model creation."""

    def test_step_types(self):
        from jarvis.workflows.models.workflow import StepType

        assert StepType.TOOL is not None
        assert StepType.INTENT is not None
        assert StepType.CONDITION is not None
        assert StepType.PARALLEL is not None
        assert StepType.LOOP is not None
        assert StepType.APPROVAL is not None

    def test_trigger_types(self):
        from jarvis.workflows.models.workflow import TriggerType

        assert TriggerType.MANUAL is not None
        assert TriggerType.SCHEDULE is not None
        assert TriggerType.FILE_WATCH is not None
        assert TriggerType.WEBHOOK is not None
        assert TriggerType.GIT is not None

    def test_create_workflow_step(self):
        from jarvis.workflows.models.workflow import WorkflowStep, StepType

        step = WorkflowStep(
            id="step-1",
            name="Execute Shell",
            step_type=StepType.TOOL,
            tool="shell_execute",
            params={"command": "echo hello"},
        )

        assert step.id == "step-1"
        assert step.step_type == StepType.TOOL
        assert step.tool == "shell_execute"

    def test_create_workflow(self):
        from jarvis.workflows.models.workflow import (
            Workflow,
            WorkflowStep,
            StepType,
        )

        workflow = Workflow(
            id="wf-001",
            name="Test Workflow",
            description="A test workflow",
            version="1.0",
            steps=[
                WorkflowStep(
                    id="s1",
                    name="Step 1",
                    step_type=StepType.TOOL,
                    tool="shell_execute",
                    params={"command": "echo test"},
                )
            ],
        )

        assert workflow.id == "wf-001"
        assert len(workflow.steps) == 1


class TestWorkflowParser:
    """Test workflow parsing functionality."""

    def test_parser_creation(self):
        from jarvis.workflows.parser import WorkflowParser

        parser = WorkflowParser()
        assert parser is not None

    def test_parse_yaml(self, temp_workflow_file):
        from jarvis.workflows.parser import WorkflowParser

        parser = WorkflowParser()
        workflow = parser.parse_file(temp_workflow_file)

        assert workflow is not None
        assert workflow.name == "test-workflow"
        assert len(workflow.steps) == 2

    def test_variable_interpolation(self):
        from jarvis.workflows.parser import WorkflowParser

        parser = WorkflowParser()

        # Test simple variable replacement
        template = "Hello ${name}!"
        context = {"name": "World"}
        result = parser._interpolate_variables(template, context)

        assert result == "Hello World!"


class TestWorkflowTriggers:
    """Test workflow trigger functionality."""

    def test_schedule_trigger(self):
        from jarvis.workflows.triggers import ScheduleTrigger

        trigger = ScheduleTrigger(
            cron_expression="0 * * * *",  # Every hour
            workflow_id="wf-001",
        )

        assert trigger.cron_expression == "0 * * * *"
        assert trigger.workflow_id == "wf-001"

    def test_file_watch_trigger(self):
        from jarvis.workflows.triggers import FileWatchTrigger

        trigger = FileWatchTrigger(
            watch_path="/tmp/watched",
            patterns=["*.py", "*.js"],
            workflow_id="wf-002",
        )

        assert trigger.watch_path == "/tmp/watched"
        assert "*.py" in trigger.patterns

    def test_trigger_manager(self):
        from jarvis.workflows.triggers import TriggerManager

        manager = TriggerManager()
        assert manager is not None
        assert hasattr(manager, "triggers")


class TestWorkflowEngine:
    """Test workflow engine functionality."""

    def test_engine_creation(self):
        from jarvis.workflows.engine import WorkflowEngine

        engine = WorkflowEngine()
        assert engine is not None

    def test_engine_singleton(self):
        from jarvis.workflows.engine import WorkflowEngine

        e1 = WorkflowEngine()
        e2 = WorkflowEngine()
        assert e1 is e2

    def test_list_workflows(self):
        from jarvis.workflows.engine import WorkflowEngine

        engine = WorkflowEngine()
        workflows = engine.list_workflows()
        assert isinstance(workflows, list)
