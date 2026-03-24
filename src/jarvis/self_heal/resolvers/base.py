"""
Base resolver interface for self-healing system.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar

from jarvis.self_heal.models.issue import Issue, IssueCategory, Resolution, ResolutionStatus
from jarvis.core.logging import get_logger


class BaseResolver(ABC):
    """
    Abstract base class for issue resolvers.

    Each resolver handles specific categories of issues.
    """

    name: ClassVar[str] = "base"
    description: ClassVar[str] = "Base resolver"

    # Issue categories this resolver can handle
    handles: ClassVar[list[IssueCategory]] = []

    def __init__(self):
        self.logger = get_logger(f"jarvis.self_heal.resolvers.{self.name}")
        self.enabled = True

    def can_handle(self, issue: Issue) -> bool:
        """Check if this resolver can handle the given issue."""
        if not self.enabled:
            return False
        if not issue.auto_resolvable:
            return False
        return issue.category in self.handles

    async def resolve(self, issue: Issue, approved: bool = False) -> Resolution:
        """
        Attempt to resolve an issue.

        Args:
            issue: The issue to resolve
            approved: Whether user has approved this resolution

        Returns:
            Resolution record with result
        """
        resolution = Resolution(
            issue_id=issue.id,
            resolver=self.name,
            status=ResolutionStatus.PENDING,
        )

        # Check approval if required
        if issue.requires_approval and not approved:
            resolution.status = ResolutionStatus.PENDING
            resolution.action_taken = "Awaiting approval"
            return resolution

        # Execute resolution
        resolution.status = ResolutionStatus.IN_PROGRESS
        resolution.started_at = datetime.utcnow()

        if approved:
            resolution.approved_by = "user"
            resolution.approved_at = datetime.utcnow()

        try:
            success, output, steps = await self._execute(issue)

            resolution.success = success
            resolution.output = output
            resolution.steps_executed = steps
            resolution.status = ResolutionStatus.SUCCESS if success else ResolutionStatus.FAILED

            if success:
                resolution.action_taken = f"Resolved: {issue.title}"
                self.logger.info(f"Resolved issue {issue.id}: {issue.title}")
            else:
                resolution.action_taken = f"Failed to resolve: {issue.title}"
                resolution.error = output
                self.logger.warning(f"Failed to resolve issue {issue.id}: {output}")

        except Exception as e:
            resolution.success = False
            resolution.status = ResolutionStatus.FAILED
            resolution.error = str(e)
            resolution.action_taken = f"Error resolving: {issue.title}"
            self.logger.error(f"Error resolving issue {issue.id}: {e}")

        resolution.completed_at = datetime.utcnow()
        return resolution

    @abstractmethod
    async def _execute(self, issue: Issue) -> tuple[bool, str, list[dict]]:
        """
        Execute the resolution.

        Args:
            issue: The issue to resolve

        Returns:
            Tuple of (success, output/error message, steps executed)
        """
        pass

    def estimate_risk(self, issue: Issue) -> str:
        """Estimate the risk level of resolving this issue."""
        return "low"


__all__ = ["BaseResolver"]
