"""
Process monitor for self-healing system.

Detects crashed or hung processes.
"""

import asyncio
from typing import ClassVar

from jarvis.self_heal.monitors.base import BaseMonitor
from jarvis.self_heal.models.issue import Issue, IssueCategory, IssueSeverity


class ProcessMonitor(BaseMonitor):
    """Monitor for process health."""

    name: ClassVar[str] = "process"
    description: ClassVar[str] = "Monitors process health and detects crashes"

    # Processes to watch (name -> expected count)
    watched_processes: dict[str, int] = {}

    # Thresholds
    cpu_threshold: float = 90.0  # %
    memory_threshold: float = 80.0  # %

    async def check(self) -> list[Issue]:
        """Check for process issues."""
        issues = []

        try:
            import psutil

            # Check overall CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.5)
            if cpu_percent > self.cpu_threshold:
                # Find top CPU consumers
                top_procs = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                    try:
                        if proc.info['cpu_percent'] and proc.info['cpu_percent'] > 20:
                            top_procs.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                issues.append(Issue(
                    category=IssueCategory.PROCESS,
                    severity=IssueSeverity.WARNING,
                    title="High CPU usage",
                    description=f"CPU usage at {cpu_percent:.1f}%",
                    details={
                        "cpu_percent": cpu_percent,
                        "top_processes": top_procs[:5],
                    },
                    source=self.name,
                    affected_resource="system",
                    suggested_resolution="Identify and stop high-CPU processes",
                    auto_resolvable=False,
                ))

            # Check memory usage
            mem = psutil.virtual_memory()
            if mem.percent > self.memory_threshold:
                # Find memory hogs
                top_mem = []
                for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
                    try:
                        if proc.info['memory_percent'] and proc.info['memory_percent'] > 5:
                            top_mem.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                top_mem.sort(key=lambda x: x.get('memory_percent', 0), reverse=True)

                issues.append(Issue(
                    category=IssueCategory.MEMORY,
                    severity=IssueSeverity.WARNING if mem.percent < 90 else IssueSeverity.ERROR,
                    title="High memory usage",
                    description=f"Memory usage at {mem.percent:.1f}%",
                    details={
                        "memory_percent": mem.percent,
                        "available_gb": round(mem.available / 1024**3, 2),
                        "top_processes": top_mem[:5],
                    },
                    source=self.name,
                    affected_resource="system",
                    suggested_resolution="Free up memory or restart memory-heavy processes",
                    auto_resolvable=False,
                ))

            # Check for zombie processes (Unix only)
            zombie_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'status']):
                try:
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        zombie_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if zombie_count > 0:
                issues.append(Issue(
                    category=IssueCategory.PROCESS,
                    severity=IssueSeverity.WARNING,
                    title="Zombie processes detected",
                    description=f"Found {zombie_count} zombie process(es)",
                    details={"zombie_count": zombie_count},
                    source=self.name,
                    affected_resource="system",
                    suggested_resolution="Reap zombie processes or restart their parent",
                    auto_resolvable=False,
                ))

            # Check watched processes
            for proc_name, expected_count in self.watched_processes.items():
                actual_count = 0
                for proc in psutil.process_iter(['name']):
                    try:
                        if proc_name.lower() in proc.info['name'].lower():
                            actual_count += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                if actual_count < expected_count:
                    issues.append(Issue(
                        category=IssueCategory.PROCESS,
                        severity=IssueSeverity.ERROR,
                        title=f"Process not running: {proc_name}",
                        description=f"Expected {expected_count} instance(s), found {actual_count}",
                        details={
                            "process_name": proc_name,
                            "expected": expected_count,
                            "actual": actual_count,
                        },
                        source=self.name,
                        affected_resource=proc_name,
                        suggested_resolution=f"Restart {proc_name}",
                        auto_resolvable=True,
                        requires_approval=True,
                    ))

        except ImportError:
            self.logger.warning("psutil not available, skipping process checks")

        return issues

    def watch_process(self, name: str, expected_count: int = 1) -> None:
        """Add a process to watch."""
        self.watched_processes[name] = expected_count

    def unwatch_process(self, name: str) -> None:
        """Remove a process from watch list."""
        self.watched_processes.pop(name, None)


__all__ = ["ProcessMonitor"]
