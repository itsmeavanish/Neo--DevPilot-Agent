"""
Base monitor interface for self-healing system.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from jarvis.self_heal.models.issue import Issue
from jarvis.core.logging import get_logger


class BaseMonitor(ABC):
    """
    Abstract base class for health monitors.

    Each monitor checks for specific types of issues.
    """

    name: str = "base"
    description: str = "Base monitor"

    def __init__(self):
        self.logger = get_logger(f"jarvis.self_heal.monitors.{self.name}")
        self.enabled = True

    @abstractmethod
    async def check(self) -> list[Issue]:
        """
        Perform health check and return any detected issues.

        Returns:
            List of Issue objects for any problems found
        """
        pass

    async def is_healthy(self) -> bool:
        """Quick check if this monitor's domain is healthy."""
        issues = await self.check()
        return not any(i.needs_action for i in issues)


__all__ = ["BaseMonitor"]
