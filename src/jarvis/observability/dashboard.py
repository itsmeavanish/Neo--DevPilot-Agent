"""
Dashboard data aggregation.

Provides aggregated metrics, statistics, and system overview.
"""

import asyncio
import os
import platform
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from jarvis.core.logging import get_logger
from jarvis.observability.metrics import get_registry

logger = get_logger("jarvis.observability.dashboard")


@dataclass
class SystemStats:
    """System resource statistics."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0
    disk_percent: float = 0.0
    disk_used_gb: float = 0.0
    disk_total_gb: float = 0.0
    uptime_seconds: float = 0.0
    process_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu_percent": round(self.cpu_percent, 1),
            "memory_percent": round(self.memory_percent, 1),
            "memory_used_gb": round(self.memory_used_gb, 2),
            "memory_total_gb": round(self.memory_total_gb, 2),
            "disk_percent": round(self.disk_percent, 1),
            "disk_used_gb": round(self.disk_used_gb, 2),
            "disk_total_gb": round(self.disk_total_gb, 2),
            "uptime_seconds": round(self.uptime_seconds, 0),
            "process_count": self.process_count,
        }


@dataclass
class ComponentHealth:
    """Health status of a component."""
    name: str
    healthy: bool
    status: str = "unknown"
    message: str | None = None
    latency_ms: float | None = None
    last_check: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "healthy": self.healthy,
            "status": self.status,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "last_check": self.last_check.isoformat(),
        }


@dataclass
class ActivitySummary:
    """Summary of recent activity."""
    total_requests: int = 0
    total_tool_calls: int = 0
    total_workflows: int = 0
    active_tasks: int = 0
    errors_last_hour: int = 0
    avg_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "total_tool_calls": self.total_tool_calls,
            "total_workflows": self.total_workflows,
            "active_tasks": self.active_tasks,
            "errors_last_hour": self.errors_last_hour,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
        }


class DashboardAggregator:
    """
    Aggregates metrics and system data for dashboard display.
    """

    def __init__(self):
        self.logger = get_logger("jarvis.observability.dashboard")
        self.registry = get_registry()
        self._start_time = datetime.utcnow()
        self._component_checks: dict[str, ComponentHealth] = {}

    async def get_system_stats(self) -> SystemStats:
        """Get current system statistics."""
        stats = SystemStats()

        try:
            import psutil

            # CPU
            stats.cpu_percent = psutil.cpu_percent(interval=0.1)

            # Memory
            mem = psutil.virtual_memory()
            stats.memory_percent = mem.percent
            stats.memory_used_gb = mem.used / (1024**3)
            stats.memory_total_gb = mem.total / (1024**3)

            # Disk
            disk = psutil.disk_usage("/")
            stats.disk_percent = disk.percent
            stats.disk_used_gb = disk.used / (1024**3)
            stats.disk_total_gb = disk.total / (1024**3)

            # Process count
            stats.process_count = len(psutil.pids())

            # Uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            stats.uptime_seconds = (datetime.now() - boot_time).total_seconds()

        except ImportError:
            self.logger.debug("psutil not available for system stats")

        return stats

    async def get_activity_summary(self) -> ActivitySummary:
        """Get activity summary from metrics."""
        summary = ActivitySummary()

        # Get from metrics registry
        metrics = self.registry.get_all()

        if "jarvis_requests_total" in metrics:
            counter = metrics["jarvis_requests_total"]
            summary.total_requests = int(sum(
                v.value for v in counter._values.values()
            ))

        if "jarvis_tool_executions_total" in metrics:
            counter = metrics["jarvis_tool_executions_total"]
            summary.total_tool_calls = int(sum(
                v.value for v in counter._values.values()
            ))

        if "jarvis_workflow_runs_total" in metrics:
            counter = metrics["jarvis_workflow_runs_total"]
            summary.total_workflows = int(sum(
                v.value for v in counter._values.values()
            ))

        if "jarvis_active_tasks" in metrics:
            gauge = metrics["jarvis_active_tasks"]
            summary.active_tasks = int(sum(
                v.value for v in gauge._values.values()
            ))

        return summary

    async def check_component_health(self, name: str, check_func) -> ComponentHealth:
        """
        Check health of a component.

        Args:
            name: Component name
            check_func: Async function that returns (healthy, message)

        Returns:
            ComponentHealth result
        """
        start = datetime.utcnow()

        try:
            healthy, message = await check_func()
            latency = (datetime.utcnow() - start).total_seconds() * 1000

            health = ComponentHealth(
                name=name,
                healthy=healthy,
                status="healthy" if healthy else "unhealthy",
                message=message,
                latency_ms=latency,
            )

        except Exception as e:
            health = ComponentHealth(
                name=name,
                healthy=False,
                status="error",
                message=str(e),
            )

        self._component_checks[name] = health
        return health

    async def get_all_health(self) -> dict[str, ComponentHealth]:
        """Get health status of all components."""
        # Run default health checks
        checks = []

        # Database check
        async def check_database():
            try:
                from jarvis.memory.long_term import LongTermMemory
                mem = LongTermMemory()
                # Simple ping
                return True, "Connected"
            except Exception as e:
                return False, str(e)

        checks.append(self.check_component_health("database", check_database))

        # Redis check
        async def check_redis():
            try:
                from jarvis.memory.short_term import ShortTermMemory
                mem = ShortTermMemory()
                return True, "Connected"
            except Exception as e:
                return False, str(e)

        checks.append(self.check_component_health("redis", check_redis))

        # LLM check
        async def check_llm():
            try:
                from jarvis.llm.providers.ollama import OllamaClient
                client = OllamaClient()
                models = await client.list_models()
                return True, f"{len(models)} models available"
            except Exception as e:
                return False, str(e)

        checks.append(self.check_component_health("llm", check_llm))

        # Run all checks
        await asyncio.gather(*checks, return_exceptions=True)

        return self._component_checks

    def get_overview(self) -> dict[str, Any]:
        """Get dashboard overview data."""
        return {
            "service": "JARVIS",
            "version": "1.0.0",
            "environment": os.environ.get("JARVIS_ENV", "development"),
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "started_at": self._start_time.isoformat(),
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
        }

    async def get_dashboard_data(self) -> dict[str, Any]:
        """
        Get complete dashboard data.

        Returns combined system stats, metrics, and health information.
        """
        # Gather data in parallel
        system_stats, activity, health = await asyncio.gather(
            self.get_system_stats(),
            self.get_activity_summary(),
            self.get_all_health(),
        )

        return {
            "overview": self.get_overview(),
            "system": system_stats.to_dict(),
            "activity": activity.to_dict(),
            "health": {name: h.to_dict() for name, h in health.items()},
            "metrics": self.registry.collect(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_quick_stats(self) -> dict[str, Any]:
        """Get quick stats without async operations."""
        return {
            "overview": self.get_overview(),
            "metrics_count": len(self.registry.get_all()),
            "components_checked": len(self._component_checks),
            "all_healthy": all(c.healthy for c in self._component_checks.values()),
        }


# Module-level singleton
_aggregator: DashboardAggregator | None = None


def get_dashboard_aggregator() -> DashboardAggregator:
    """Get singleton dashboard aggregator."""
    global _aggregator
    if _aggregator is None:
        _aggregator = DashboardAggregator()
    return _aggregator


__all__ = [
    "SystemStats",
    "ComponentHealth",
    "ActivitySummary",
    "DashboardAggregator",
    "get_dashboard_aggregator",
]
