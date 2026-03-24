"""
Workflow trigger system.

Handles triggering workflows from various sources: schedules, file changes, webhooks, etc.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Callable, Awaitable, Any

from jarvis.core.logging import get_logger
from jarvis.workflows.models.workflow import (
    Workflow, WorkflowTrigger, TriggerType,
)

logger = get_logger("jarvis.workflows.triggers")


# Callback for when trigger fires
TriggerCallback = Callable[[Workflow, WorkflowTrigger, dict], Awaitable[None]]


class ScheduleTrigger:
    """
    Schedule-based trigger using cron expressions.
    """

    def __init__(self):
        self.logger = get_logger("jarvis.workflows.triggers.schedule")
        self._tasks: dict[str, asyncio.Task] = {}
        self._callback: TriggerCallback | None = None

    def set_callback(self, callback: TriggerCallback) -> None:
        """Set the callback to invoke when trigger fires."""
        self._callback = callback

    async def register(self, workflow: Workflow, trigger: WorkflowTrigger) -> bool:
        """Register a scheduled workflow."""
        if trigger.trigger_type != TriggerType.SCHEDULE:
            return False

        if not trigger.schedule:
            self.logger.warning(f"No schedule defined for trigger {trigger.id}")
            return False

        key = f"{workflow.id}:{trigger.id}"

        # Cancel existing task if any
        if key in self._tasks:
            self._tasks[key].cancel()

        # Start new schedule task
        task = asyncio.create_task(
            self._schedule_loop(workflow, trigger)
        )
        self._tasks[key] = task

        self.logger.info(f"Registered schedule trigger: {trigger.schedule}")
        return True

    async def unregister(self, workflow_id: str, trigger_id: str) -> bool:
        """Unregister a scheduled workflow."""
        key = f"{workflow_id}:{trigger_id}"
        if key in self._tasks:
            self._tasks[key].cancel()
            del self._tasks[key]
            return True
        return False

    async def _schedule_loop(
        self,
        workflow: Workflow,
        trigger: WorkflowTrigger,
    ) -> None:
        """Main loop for scheduled execution."""
        try:
            while trigger.enabled:
                # Calculate next run time
                next_run = self._get_next_run(trigger.schedule)
                if not next_run:
                    await asyncio.sleep(60)
                    continue

                # Wait until next run
                now = datetime.utcnow()
                wait_seconds = (next_run - now).total_seconds()

                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

                # Fire trigger
                if self._callback and trigger.enabled:
                    trigger.last_triggered = datetime.utcnow()
                    trigger.trigger_count += 1
                    await self._callback(workflow, trigger, {
                        "scheduled_time": next_run.isoformat(),
                        "schedule": trigger.schedule,
                    })

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Schedule trigger error: {e}")

    def _get_next_run(self, cron_expr: str) -> datetime | None:
        """Get next run time from cron expression."""
        try:
            from croniter import croniter
            cron = croniter(cron_expr, datetime.utcnow())
            return cron.get_next(datetime)
        except ImportError:
            # Simple fallback - run every minute
            self.logger.warning("croniter not installed, using 1-minute interval")
            return datetime.utcnow()
        except Exception as e:
            self.logger.error(f"Invalid cron expression '{cron_expr}': {e}")
            return None

    async def stop_all(self) -> None:
        """Stop all scheduled triggers."""
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()


class FileWatchTrigger:
    """
    File system watch trigger.
    """

    def __init__(self):
        self.logger = get_logger("jarvis.workflows.triggers.file_watch")
        self._watchers: dict[str, asyncio.Task] = {}
        self._callback: TriggerCallback | None = None

    def set_callback(self, callback: TriggerCallback) -> None:
        """Set the callback to invoke when trigger fires."""
        self._callback = callback

    async def register(self, workflow: Workflow, trigger: WorkflowTrigger) -> bool:
        """Register a file watch trigger."""
        if trigger.trigger_type != TriggerType.FILE_WATCH:
            return False

        if not trigger.watch_paths:
            self.logger.warning(f"No paths defined for trigger {trigger.id}")
            return False

        key = f"{workflow.id}:{trigger.id}"

        # Cancel existing watcher if any
        if key in self._watchers:
            self._watchers[key].cancel()

        # Start new watcher
        task = asyncio.create_task(
            self._watch_loop(workflow, trigger)
        )
        self._watchers[key] = task

        self.logger.info(f"Registered file watch: {trigger.watch_paths}")
        return True

    async def unregister(self, workflow_id: str, trigger_id: str) -> bool:
        """Unregister a file watch trigger."""
        key = f"{workflow_id}:{trigger_id}"
        if key in self._watchers:
            self._watchers[key].cancel()
            del self._watchers[key]
            return True
        return False

    async def _watch_loop(
        self,
        workflow: Workflow,
        trigger: WorkflowTrigger,
    ) -> None:
        """Main loop for file watching."""
        try:
            # Try to use watchdog if available
            try:
                from watchdog.observers import Observer
                from watchdog.events import FileSystemEventHandler

                handler = _WatchdogHandler(
                    workflow, trigger, self._callback,
                    trigger.watch_patterns,
                    trigger.watch_events,
                )

                observer = Observer()
                for path in trigger.watch_paths:
                    observer.schedule(handler, path, recursive=True)

                observer.start()

                while trigger.enabled:
                    await asyncio.sleep(1)

                observer.stop()
                observer.join()

            except ImportError:
                # Fallback to polling
                self.logger.warning("watchdog not installed, using polling")
                await self._poll_files(workflow, trigger)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"File watch trigger error: {e}")

    async def _poll_files(
        self,
        workflow: Workflow,
        trigger: WorkflowTrigger,
    ) -> None:
        """Poll files for changes (fallback)."""
        import fnmatch

        # Track file modification times
        mtimes: dict[str, float] = {}

        while trigger.enabled:
            for watch_path in trigger.watch_paths:
                path = Path(watch_path)
                if not path.exists():
                    continue

                files = path.rglob("*") if path.is_dir() else [path]

                for file in files:
                    if not file.is_file():
                        continue

                    # Check patterns
                    if not any(fnmatch.fnmatch(file.name, p) for p in trigger.watch_patterns):
                        continue

                    try:
                        mtime = file.stat().st_mtime
                        file_key = str(file)

                        if file_key in mtimes:
                            if mtime > mtimes[file_key]:
                                # File modified
                                if "modified" in trigger.watch_events and self._callback:
                                    trigger.last_triggered = datetime.utcnow()
                                    trigger.trigger_count += 1
                                    await self._callback(workflow, trigger, {
                                        "event": "modified",
                                        "path": str(file),
                                    })
                        else:
                            # New file
                            if "created" in trigger.watch_events and self._callback:
                                trigger.last_triggered = datetime.utcnow()
                                trigger.trigger_count += 1
                                await self._callback(workflow, trigger, {
                                    "event": "created",
                                    "path": str(file),
                                })

                        mtimes[file_key] = mtime

                    except (OSError, IOError):
                        pass

            await asyncio.sleep(2)

    async def stop_all(self) -> None:
        """Stop all file watchers."""
        for task in self._watchers.values():
            task.cancel()
        self._watchers.clear()


class _WatchdogHandler:
    """Watchdog event handler."""

    def __init__(
        self,
        workflow: Workflow,
        trigger: WorkflowTrigger,
        callback: TriggerCallback | None,
        patterns: list[str],
        events: list[str],
    ):
        self.workflow = workflow
        self.trigger = trigger
        self.callback = callback
        self.patterns = patterns
        self.events = events
        self._loop = asyncio.get_event_loop()

    def on_any_event(self, event):
        """Handle any file system event."""
        import fnmatch

        if event.is_directory:
            return

        # Check event type
        event_type = event.event_type
        if event_type not in self.events:
            return

        # Check patterns
        filename = Path(event.src_path).name
        if not any(fnmatch.fnmatch(filename, p) for p in self.patterns):
            return

        # Fire callback
        if self.callback:
            self.trigger.last_triggered = datetime.utcnow()
            self.trigger.trigger_count += 1
            asyncio.run_coroutine_threadsafe(
                self.callback(self.workflow, self.trigger, {
                    "event": event_type,
                    "path": event.src_path,
                }),
                self._loop,
            )


class TriggerManager:
    """
    Manages all workflow triggers.
    """

    def __init__(self):
        self.logger = get_logger("jarvis.workflows.triggers")

        # Individual trigger handlers
        self.schedule = ScheduleTrigger()
        self.file_watch = FileWatchTrigger()

        # Registered workflows and triggers
        self._workflows: dict[str, Workflow] = {}

        # Main callback
        self._callback: TriggerCallback | None = None

    def set_callback(self, callback: TriggerCallback) -> None:
        """Set the callback for all triggers."""
        self._callback = callback
        self.schedule.set_callback(callback)
        self.file_watch.set_callback(callback)

    async def register_workflow(self, workflow: Workflow) -> int:
        """
        Register all triggers for a workflow.

        Returns number of triggers registered.
        """
        self._workflows[workflow.id] = workflow
        count = 0

        for trigger in workflow.triggers:
            if not trigger.enabled:
                continue

            if trigger.trigger_type == TriggerType.SCHEDULE:
                if await self.schedule.register(workflow, trigger):
                    count += 1
            elif trigger.trigger_type == TriggerType.FILE_WATCH:
                if await self.file_watch.register(workflow, trigger):
                    count += 1
            # Webhooks are handled differently (via API)

        return count

    async def unregister_workflow(self, workflow_id: str) -> bool:
        """Unregister all triggers for a workflow."""
        workflow = self._workflows.pop(workflow_id, None)
        if not workflow:
            return False

        for trigger in workflow.triggers:
            if trigger.trigger_type == TriggerType.SCHEDULE:
                await self.schedule.unregister(workflow_id, trigger.id)
            elif trigger.trigger_type == TriggerType.FILE_WATCH:
                await self.file_watch.unregister(workflow_id, trigger.id)

        return True

    async def stop_all(self) -> None:
        """Stop all triggers."""
        await self.schedule.stop_all()
        await self.file_watch.stop_all()
        self._workflows.clear()

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        """Get a registered workflow."""
        return self._workflows.get(workflow_id)


# Module-level singleton
_manager: TriggerManager | None = None


def get_trigger_manager() -> TriggerManager:
    """Get singleton trigger manager."""
    global _manager
    if _manager is None:
        _manager = TriggerManager()
    return _manager


__all__ = [
    "ScheduleTrigger",
    "FileWatchTrigger",
    "TriggerManager",
    "get_trigger_manager",
]
