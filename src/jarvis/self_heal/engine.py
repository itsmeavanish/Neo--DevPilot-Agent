"""
Self-healing engine.

Coordinates monitors, detects issues, and orchestrates resolutions.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Callable, Awaitable

from jarvis.core.logging import get_logger
from jarvis.self_heal.models.issue import (
    Issue, Resolution, HealthStatus,
    IssueSeverity, ResolutionStatus,
)
from jarvis.self_heal.monitors.base import BaseMonitor
from jarvis.self_heal.monitors.process import ProcessMonitor
from jarvis.self_heal.monitors.port import PortMonitor
from jarvis.self_heal.monitors.disk import DiskMonitor
from jarvis.self_heal.monitors.dependency import DependencyMonitor
from jarvis.self_heal.resolvers.base import BaseResolver
from jarvis.self_heal.resolvers.restart import RestartResolver
from jarvis.self_heal.resolvers.port_free import PortFreeResolver
from jarvis.self_heal.resolvers.dep_install import DependencyInstallResolver
from jarvis.self_heal.resolvers.cleanup import CleanupResolver


logger = get_logger("jarvis.self_heal.engine")


# Type for approval callback
ApprovalCallback = Callable[[Issue, str], Awaitable[bool]]


class SelfHealEngine:
    """
    Self-healing engine that monitors system health and auto-repairs issues.

    Usage:
        engine = SelfHealEngine()
        engine.set_project_root("/path/to/project")

        # Run health check
        status = await engine.check_health()

        # Auto-resolve issues (with approval callback)
        async def approve(issue, action):
            return input(f"Approve {action}? (y/n): ").lower() == 'y'

        results = await engine.auto_resolve(approval_callback=approve)
    """

    def __init__(self):
        self.monitors: list[BaseMonitor] = []
        self.resolvers: list[BaseResolver] = []

        # Current state
        self.active_issues: dict[str, Issue] = {}
        self.resolution_history: list[Resolution] = []

        # Configuration
        self.project_root: Path | None = None
        self.auto_resolve_enabled: bool = False
        self.require_approval: bool = True

        # Background monitoring
        self._monitor_task: asyncio.Task | None = None
        self._monitor_interval: float = 60.0  # seconds

        # Initialize default monitors and resolvers
        self._init_defaults()

    def _init_defaults(self):
        """Initialize default monitors and resolvers."""
        # Monitors
        self.monitors = [
            ProcessMonitor(),
            PortMonitor(),
            DiskMonitor(),
            DependencyMonitor(),
        ]

        # Resolvers
        self.resolvers = [
            RestartResolver(),
            PortFreeResolver(),
            DependencyInstallResolver(),
            CleanupResolver(),
        ]

    def set_project_root(self, path: str | Path) -> None:
        """Set the project root for monitoring."""
        self.project_root = Path(path)

        # Update monitors that need project context
        for monitor in self.monitors:
            if hasattr(monitor, "set_project_root"):
                monitor.set_project_root(self.project_root)

    def set_ports_to_monitor(self, ports: list[int]) -> None:
        """Set specific ports to monitor."""
        for monitor in self.monitors:
            if isinstance(monitor, PortMonitor):
                monitor.ports = set(ports)
                break

    async def check_health(self) -> HealthStatus:
        """
        Run all monitors and return system health status.

        Returns:
            HealthStatus with all detected issues
        """
        all_issues: list[Issue] = []
        checks_performed: dict[str, bool] = {}

        for monitor in self.monitors:
            if not monitor.enabled:
                checks_performed[monitor.name] = False
                continue

            try:
                issues = await monitor.check()
                all_issues.extend(issues)
                checks_performed[monitor.name] = True
                logger.debug(f"Monitor {monitor.name}: {len(issues)} issues found")
            except Exception as e:
                logger.error(f"Monitor {monitor.name} failed: {e}")
                checks_performed[monitor.name] = False

        # Update active issues
        for issue in all_issues:
            self.active_issues[issue.id] = issue

        # Build health status
        status = HealthStatus(
            healthy=not any(i.needs_action for i in all_issues),
            issues=all_issues,
            warnings=sum(1 for i in all_issues if i.severity == IssueSeverity.WARNING),
            errors=sum(1 for i in all_issues if i.severity == IssueSeverity.ERROR),
            critical=sum(1 for i in all_issues if i.severity == IssueSeverity.CRITICAL),
            last_check=datetime.utcnow(),
            checks_performed=checks_performed,
        )

        return status

    def find_resolver(self, issue: Issue) -> BaseResolver | None:
        """Find a resolver that can handle the given issue."""
        for resolver in self.resolvers:
            if resolver.can_handle(issue):
                return resolver
        return None

    async def resolve_issue(
        self,
        issue: Issue,
        approved: bool = False,
        approval_callback: ApprovalCallback | None = None,
    ) -> Resolution:
        """
        Attempt to resolve a specific issue.

        Args:
            issue: The issue to resolve
            approved: Whether the resolution is pre-approved
            approval_callback: Async function to request approval

        Returns:
            Resolution record
        """
        resolver = self.find_resolver(issue)

        if not resolver:
            return Resolution(
                issue_id=issue.id,
                status=ResolutionStatus.MANUAL,
                action_taken="No auto-resolver available",
                error="No resolver can handle this issue type",
            )

        # Handle approval
        if issue.requires_approval and not approved:
            if approval_callback:
                action = resolver.description
                approved = await approval_callback(issue, action)

            if not approved:
                return Resolution(
                    issue_id=issue.id,
                    resolver=resolver.name,
                    status=ResolutionStatus.PENDING,
                    action_taken="Awaiting approval",
                )

        # Execute resolution
        resolution = await resolver.resolve(issue, approved=approved)

        # Track history
        self.resolution_history.append(resolution)

        # Remove from active issues if resolved
        if resolution.success and issue.id in self.active_issues:
            self.active_issues[issue.id].resolved_at = datetime.utcnow()
            del self.active_issues[issue.id]

        return resolution

    async def auto_resolve(
        self,
        approval_callback: ApprovalCallback | None = None,
        max_issues: int = 10,
    ) -> list[Resolution]:
        """
        Attempt to auto-resolve all current issues.

        Args:
            approval_callback: Async function to request approval for each resolution
            max_issues: Maximum number of issues to resolve

        Returns:
            List of resolution records
        """
        # Run health check first
        await self.check_health()

        resolutions: list[Resolution] = []

        # Sort issues by severity (critical first)
        sorted_issues = sorted(
            self.active_issues.values(),
            key=lambda i: ["info", "warning", "error", "critical"].index(i.severity.value),
            reverse=True,
        )

        for issue in sorted_issues[:max_issues]:
            if not issue.auto_resolvable:
                continue

            resolution = await self.resolve_issue(
                issue,
                approval_callback=approval_callback,
            )
            resolutions.append(resolution)

            # Stop if we hit failures
            if resolution.status == ResolutionStatus.FAILED:
                logger.warning(f"Resolution failed for {issue.id}, stopping auto-resolve")
                break

        return resolutions

    async def start_monitoring(self, interval: float = 60.0) -> None:
        """
        Start background health monitoring.

        Args:
            interval: Seconds between health checks
        """
        if self._monitor_task and not self._monitor_task.done():
            logger.warning("Monitoring already running")
            return

        self._monitor_interval = interval
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Started health monitoring (interval: {interval}s)")

    async def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
            logger.info("Stopped health monitoring")

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while True:
            try:
                status = await self.check_health()

                if not status.healthy:
                    logger.warning(
                        f"Health check: {status.errors} errors, "
                        f"{status.critical} critical issues"
                    )

                    # Auto-resolve if enabled
                    if self.auto_resolve_enabled and not self.require_approval:
                        await self.auto_resolve()

                await asyncio.sleep(self._monitor_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(self._monitor_interval)

    def get_active_issues(self) -> list[Issue]:
        """Get all currently active issues."""
        return list(self.active_issues.values())

    def get_resolution_history(self, limit: int = 50) -> list[Resolution]:
        """Get recent resolution history."""
        return self.resolution_history[-limit:]

    def clear_resolved_issues(self) -> int:
        """Clear issues that have been resolved."""
        initial_count = len(self.active_issues)
        self.active_issues = {
            id: issue for id, issue in self.active_issues.items()
            if issue.resolved_at is None
        }
        return initial_count - len(self.active_issues)


# ═══════════════════════════════════════════════════════════════
# Module-level singleton
# ═══════════════════════════════════════════════════════════════

_engine: SelfHealEngine | None = None


def get_self_heal_engine() -> SelfHealEngine:
    """Get the singleton self-heal engine instance."""
    global _engine
    if _engine is None:
        _engine = SelfHealEngine()
    return _engine


__all__ = ["SelfHealEngine", "get_self_heal_engine", "ApprovalCallback"]
