"""
Workflow engine.

Main orchestrator for workflow management, execution, and persistence.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.core.logging import get_logger
from jarvis.workflows.models.workflow import (
    Workflow, WorkflowRun, WorkflowTrigger, TriggerType,
)
from jarvis.workflows.parser import WorkflowParser, parse_workflow
from jarvis.workflows.executor import WorkflowExecutor, get_workflow_executor
from jarvis.workflows.triggers import TriggerManager, get_trigger_manager

logger = get_logger("jarvis.workflows.engine")


class WorkflowEngine:
    """
    Main workflow engine.

    Provides unified interface for:
    - Workflow CRUD operations
    - Workflow execution
    - Trigger management
    - Persistence
    - Run history
    """

    def __init__(
        self,
        storage_path: str | Path | None = None,
        executor: WorkflowExecutor | None = None,
        trigger_manager: TriggerManager | None = None,
    ):
        self.logger = get_logger("jarvis.workflows.engine")

        # Components
        self.parser = WorkflowParser()
        self.executor = executor or get_workflow_executor()
        self.triggers = trigger_manager or get_trigger_manager()

        # Storage
        self.storage_path = Path(storage_path) if storage_path else None
        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)

        # In-memory storage
        self.workflows: dict[str, Workflow] = {}
        self.run_history: list[WorkflowRun] = []
        self.max_history = 100

        # Wire up callbacks
        self._setup_callbacks()

    def _setup_callbacks(self) -> None:
        """Wire up internal callbacks."""
        # When trigger fires, execute workflow
        async def on_trigger(
            workflow: Workflow,
            trigger: WorkflowTrigger,
            data: dict,
        ):
            self.logger.info(f"Trigger fired for workflow '{workflow.name}'")
            await self.run(workflow.id, trigger.trigger_type, data)

        self.triggers.set_callback(on_trigger)

    # ═══════════════════════════════════════════════════════════════
    # Workflow CRUD
    # ═══════════════════════════════════════════════════════════════

    def create(self, definition: str | dict | Path) -> Workflow:
        """
        Create a new workflow from definition.

        Args:
            definition: YAML/JSON string, dict, or file path

        Returns:
            Created Workflow
        """
        workflow = parse_workflow(definition)

        # Check for duplicates
        if workflow.id in self.workflows:
            raise ValueError(f"Workflow with ID '{workflow.id}' already exists")

        self.workflows[workflow.id] = workflow
        self._save_workflow(workflow)

        self.logger.info(f"Created workflow: {workflow.name} ({workflow.id})")
        return workflow

    def get(self, workflow_id: str) -> Workflow | None:
        """Get workflow by ID."""
        return self.workflows.get(workflow_id)

    def get_by_name(self, name: str) -> Workflow | None:
        """Get workflow by name."""
        for wf in self.workflows.values():
            if wf.name == name:
                return wf
        return None

    def list(
        self,
        enabled_only: bool = False,
        tags: list[str] | None = None,
    ) -> list[Workflow]:
        """
        List all workflows.

        Args:
            enabled_only: Only return enabled workflows
            tags: Filter by tags

        Returns:
            List of workflows
        """
        workflows = list(self.workflows.values())

        if enabled_only:
            workflows = [w for w in workflows if w.enabled]

        if tags:
            workflows = [w for w in workflows if all(t in w.tags for t in tags)]

        return workflows

    def update(self, workflow_id: str, updates: dict) -> Workflow:
        """
        Update a workflow.

        Args:
            workflow_id: ID of workflow to update
            updates: Fields to update

        Returns:
            Updated workflow
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        # Apply updates
        for key, value in updates.items():
            if hasattr(workflow, key):
                setattr(workflow, key, value)

        workflow.updated_at = datetime.utcnow()
        self._save_workflow(workflow)

        self.logger.info(f"Updated workflow: {workflow.name}")
        return workflow

    def delete(self, workflow_id: str) -> bool:
        """
        Delete a workflow.

        Args:
            workflow_id: ID of workflow to delete

        Returns:
            True if deleted
        """
        workflow = self.workflows.pop(workflow_id, None)
        if not workflow:
            return False

        # Unregister triggers
        asyncio.create_task(self.triggers.unregister_workflow(workflow_id))

        # Delete persisted file
        if self.storage_path:
            file_path = self.storage_path / f"{workflow_id}.json"
            file_path.unlink(missing_ok=True)

        self.logger.info(f"Deleted workflow: {workflow.name}")
        return True

    # ═══════════════════════════════════════════════════════════════
    # Workflow Execution
    # ═══════════════════════════════════════════════════════════════

    async def run(
        self,
        workflow_id: str,
        trigger_type: TriggerType = TriggerType.MANUAL,
        trigger_data: dict | None = None,
        variables: dict | None = None,
    ) -> WorkflowRun:
        """
        Run a workflow.

        Args:
            workflow_id: ID of workflow to run
            trigger_type: What triggered this run
            trigger_data: Data from trigger
            variables: Runtime variables

        Returns:
            WorkflowRun with results
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        if not workflow.enabled:
            raise ValueError(f"Workflow '{workflow.name}' is disabled")

        # Execute
        run = await self.executor.execute(
            workflow,
            trigger_type=trigger_type,
            trigger_data=trigger_data,
            variables=variables,
        )

        # Store in history
        self.run_history.append(run)
        if len(self.run_history) > self.max_history:
            self.run_history = self.run_history[-self.max_history:]

        # Update workflow stats
        self._save_workflow(workflow)

        return run

    async def run_by_name(
        self,
        name: str,
        variables: dict | None = None,
    ) -> WorkflowRun:
        """Run a workflow by name."""
        workflow = self.get_by_name(name)
        if not workflow:
            raise ValueError(f"Workflow not found: {name}")
        return await self.run(workflow.id, variables=variables)

    async def cancel(self, run_id: str) -> bool:
        """Cancel a running workflow."""
        return await self.executor.cancel(run_id)

    def get_run(self, run_id: str) -> WorkflowRun | None:
        """Get a workflow run by ID."""
        # Check active runs
        run = self.executor.get_run(run_id)
        if run:
            return run

        # Check history
        for run in self.run_history:
            if run.id == run_id:
                return run

        return None

    def get_run_history(
        self,
        workflow_id: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowRun]:
        """
        Get run history.

        Args:
            workflow_id: Filter by workflow
            limit: Maximum results

        Returns:
            List of runs
        """
        runs = self.run_history

        if workflow_id:
            runs = [r for r in runs if r.workflow_id == workflow_id]

        return runs[-limit:]

    # ═══════════════════════════════════════════════════════════════
    # Trigger Management
    # ═══════════════════════════════════════════════════════════════

    async def enable_triggers(self, workflow_id: str) -> int:
        """
        Enable all triggers for a workflow.

        Returns number of triggers enabled.
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        return await self.triggers.register_workflow(workflow)

    async def disable_triggers(self, workflow_id: str) -> bool:
        """Disable all triggers for a workflow."""
        return await self.triggers.unregister_workflow(workflow_id)

    async def enable_all_triggers(self) -> int:
        """Enable triggers for all workflows."""
        count = 0
        for workflow in self.workflows.values():
            if workflow.enabled and workflow.triggers:
                count += await self.triggers.register_workflow(workflow)
        return count

    async def disable_all_triggers(self) -> None:
        """Disable all triggers."""
        await self.triggers.stop_all()

    # ═══════════════════════════════════════════════════════════════
    # Persistence
    # ═══════════════════════════════════════════════════════════════

    def _save_workflow(self, workflow: Workflow) -> None:
        """Save workflow to storage."""
        if not self.storage_path:
            return

        file_path = self.storage_path / f"{workflow.id}.json"
        file_path.write_text(
            json.dumps(workflow.to_dict(), indent=2),
            encoding="utf-8",
        )

    def load_from_storage(self) -> int:
        """
        Load workflows from storage.

        Returns number of workflows loaded.
        """
        if not self.storage_path:
            return 0

        count = 0
        for file_path in self.storage_path.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                workflow = Workflow.from_dict(data)
                self.workflows[workflow.id] = workflow
                count += 1
            except Exception as e:
                self.logger.error(f"Failed to load workflow from {file_path}: {e}")

        self.logger.info(f"Loaded {count} workflows from storage")
        return count

    def load_from_directory(self, directory: str | Path) -> int:
        """
        Load workflows from a directory of YAML/JSON files.

        Returns number of workflows loaded.
        """
        directory = Path(directory)
        if not directory.exists():
            return 0

        count = 0
        for file_path in directory.glob("*.yaml"):
            try:
                workflow = parse_workflow(file_path)
                self.workflows[workflow.id] = workflow
                count += 1
            except Exception as e:
                self.logger.error(f"Failed to load workflow from {file_path}: {e}")

        for file_path in directory.glob("*.yml"):
            try:
                workflow = parse_workflow(file_path)
                self.workflows[workflow.id] = workflow
                count += 1
            except Exception as e:
                self.logger.error(f"Failed to load workflow from {file_path}: {e}")

        for file_path in directory.glob("*.json"):
            try:
                workflow = parse_workflow(file_path)
                self.workflows[workflow.id] = workflow
                count += 1
            except Exception as e:
                self.logger.error(f"Failed to load workflow from {file_path}: {e}")

        self.logger.info(f"Loaded {count} workflows from {directory}")
        return count


# Import asyncio for async task creation
import asyncio


# Module-level singleton
_engine: WorkflowEngine | None = None


def get_workflow_engine() -> WorkflowEngine:
    """Get singleton workflow engine."""
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
    return _engine


__all__ = ["WorkflowEngine", "get_workflow_engine"]
