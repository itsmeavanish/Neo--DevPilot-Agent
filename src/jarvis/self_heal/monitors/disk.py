"""
Disk monitor for self-healing system.

Monitors disk space and detects low space conditions.
"""

import shutil
from pathlib import Path
from typing import ClassVar

from jarvis.self_heal.monitors.base import BaseMonitor
from jarvis.self_heal.models.issue import Issue, IssueCategory, IssueSeverity


class DiskMonitor(BaseMonitor):
    """Monitor for disk space."""

    name: ClassVar[str] = "disk"
    description: ClassVar[str] = "Monitors disk space and detects low space conditions"

    # Thresholds (percentage used)
    warning_threshold: float = 80.0
    error_threshold: float = 90.0
    critical_threshold: float = 95.0

    # Minimum free space in GB
    min_free_gb: float = 5.0

    # Paths to monitor
    monitored_paths: list[str] = []

    async def check(self) -> list[Issue]:
        """Check for disk space issues."""
        issues = []

        # Get paths to check
        paths_to_check = set()

        # Add monitored paths
        for p in self.monitored_paths:
            paths_to_check.add(Path(p).resolve())

        # Add current drive root
        paths_to_check.add(Path.cwd().anchor)

        # Add common important paths
        try:
            import psutil
            for part in psutil.disk_partitions():
                if 'cdrom' not in part.opts.lower() and 'removable' not in part.opts.lower():
                    paths_to_check.add(part.mountpoint)
            use_psutil = True
        except ImportError:
            use_psutil = False

        # Check each path
        for path in paths_to_check:
            try:
                if use_psutil:
                    import psutil
                    usage = psutil.disk_usage(str(path))
                    total_gb = usage.total / 1024**3
                    free_gb = usage.free / 1024**3
                    used_percent = usage.percent
                else:
                    total, used, free = shutil.disk_usage(path)
                    total_gb = total / 1024**3
                    free_gb = free / 1024**3
                    used_percent = (used / total) * 100

                # Determine severity
                severity = None
                if used_percent >= self.critical_threshold or free_gb < 1:
                    severity = IssueSeverity.CRITICAL
                elif used_percent >= self.error_threshold or free_gb < self.min_free_gb:
                    severity = IssueSeverity.ERROR
                elif used_percent >= self.warning_threshold:
                    severity = IssueSeverity.WARNING

                if severity:
                    issues.append(Issue(
                        category=IssueCategory.DISK,
                        severity=severity,
                        title=f"Low disk space on {path}",
                        description=f"{free_gb:.1f} GB free ({100-used_percent:.1f}% available)",
                        details={
                            "path": str(path),
                            "total_gb": round(total_gb, 2),
                            "free_gb": round(free_gb, 2),
                            "used_percent": round(used_percent, 1),
                        },
                        source=self.name,
                        affected_resource=str(path),
                        suggested_resolution=self._get_cleanup_suggestion(path),
                        auto_resolvable=severity != IssueSeverity.CRITICAL,
                        requires_approval=True,
                    ))

            except (OSError, PermissionError) as e:
                self.logger.debug(f"Cannot check disk {path}: {e}")

        return issues

    def _get_cleanup_suggestion(self, path: str) -> str:
        """Get cleanup suggestions for a path."""
        suggestions = [
            "Clear temporary files",
            "Empty recycle bin/trash",
            "Remove unused Docker images (docker system prune)",
            "Clear npm/pip cache",
            "Remove old log files",
        ]
        return "; ".join(suggestions)

    async def get_large_directories(
        self,
        path: str | Path,
        limit: int = 10,
        min_size_mb: float = 100,
    ) -> list[dict]:
        """Find largest directories under a path."""
        import asyncio

        path = Path(path)
        sizes = []

        def scan():
            for item in path.iterdir():
                if item.is_dir():
                    try:
                        total = sum(
                            f.stat().st_size
                            for f in item.rglob('*')
                            if f.is_file()
                        )
                        if total > min_size_mb * 1024 * 1024:
                            sizes.append({
                                "path": str(item),
                                "size_mb": round(total / 1024 / 1024, 2),
                            })
                    except (OSError, PermissionError):
                        continue

        await asyncio.to_thread(scan)

        sizes.sort(key=lambda x: x["size_mb"], reverse=True)
        return sizes[:limit]

    def add_monitored_path(self, path: str) -> None:
        """Add a path to monitor."""
        if path not in self.monitored_paths:
            self.monitored_paths.append(path)


__all__ = ["DiskMonitor"]
