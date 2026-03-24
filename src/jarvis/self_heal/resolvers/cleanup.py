"""
Cleanup resolver for disk space and resource issues.

Handles disk cleanup, cache clearing, and resource recovery.
"""

import asyncio
import subprocess
import shutil
from pathlib import Path
from typing import ClassVar

from jarvis.self_heal.resolvers.base import BaseResolver
from jarvis.self_heal.models.issue import Issue, IssueCategory


class CleanupResolver(BaseResolver):
    """Resolver for disk and resource cleanup."""

    name: ClassVar[str] = "cleanup"
    description: ClassVar[str] = "Cleans up disk space and recovers resources"
    handles: ClassVar[list[IssueCategory]] = [IssueCategory.DISK, IssueCategory.MEMORY]

    # Safe directories to clean within projects
    SAFE_CLEAN_DIRS: ClassVar[list[str]] = [
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "coverage",
        ".coverage",
        ".tox",
        "*.egg-info",
    ]

    # Cache directories that can be cleaned
    CACHE_DIRS: ClassVar[dict[str, str]] = {
        "npm": "~/.npm/_cacache",
        "pip": "~/.cache/pip",
        "yarn": "~/.cache/yarn",
        "pnpm": "~/.local/share/pnpm/store",
    }

    async def _execute(self, issue: Issue) -> tuple[bool, str, list[dict]]:
        """Execute cleanup operation."""
        steps = []

        if issue.category == IssueCategory.DISK:
            return await self._handle_disk_cleanup(issue, steps)
        elif issue.category == IssueCategory.MEMORY:
            return await self._handle_memory_cleanup(issue, steps)

        return False, f"Unknown cleanup category: {issue.category}", steps

    async def _handle_disk_cleanup(
        self, issue: Issue, steps: list[dict]
    ) -> tuple[bool, str, list[dict]]:
        """Handle disk space cleanup."""
        total_freed = 0

        # Get paths to clean from issue details
        large_dirs = issue.details.get("large_directories", [])
        project_path = issue.details.get("path")

        # Clean project-specific directories
        if project_path:
            project_freed = await self._clean_project(Path(project_path), steps)
            total_freed += project_freed

        # Clean suggested large directories (if they're safe)
        for dir_info in large_dirs[:5]:  # Limit to top 5
            dir_path = dir_info.get("path") if isinstance(dir_info, dict) else str(dir_info)
            if self._is_safe_to_clean(dir_path):
                freed = await self._clean_directory(Path(dir_path), steps)
                total_freed += freed

        # Clean package manager caches
        cache_freed = await self._clean_caches(steps)
        total_freed += cache_freed

        if total_freed > 0:
            freed_mb = total_freed / (1024 * 1024)
            return True, f"Freed {freed_mb:.1f} MB of disk space", steps

        return False, "No disk space freed", steps

    async def _handle_memory_cleanup(
        self, issue: Issue, steps: list[dict]
    ) -> tuple[bool, str, list[dict]]:
        """Handle memory cleanup (kill high-memory processes)."""
        # This is handled more carefully - typically just suggest, don't auto-execute
        process_name = issue.affected_resource
        pid = issue.details.get("pid")

        if pid and process_name:
            # Only kill if explicitly marked as safe
            if issue.details.get("safe_to_kill", False):
                kill_step = await self._kill_process(pid, process_name)
                steps.append(kill_step)
                return kill_step["success"], kill_step["output"], steps

        return False, "Memory cleanup requires manual intervention", steps

    async def _clean_project(self, project_path: Path, steps: list[dict]) -> int:
        """Clean a project directory of build artifacts and caches."""
        total_freed = 0

        for pattern in self.SAFE_CLEAN_DIRS:
            if "*" in pattern:
                # Handle wildcard patterns
                for match in project_path.rglob(pattern):
                    if match.is_dir():
                        freed = await self._remove_directory(match, steps)
                        total_freed += freed
            else:
                target = project_path / pattern
                if target.exists() and target.is_dir():
                    freed = await self._remove_directory(target, steps)
                    total_freed += freed

        return total_freed

    async def _clean_directory(self, path: Path, steps: list[dict]) -> int:
        """Clean a specific directory."""
        if not path.exists():
            return 0

        if path.is_dir():
            return await self._remove_directory(path, steps)

        return 0

    async def _remove_directory(self, path: Path, steps: list[dict]) -> int:
        """Remove a directory and return bytes freed."""
        step = {
            "action": f"remove {path.name}",
            "path": str(path),
            "success": False,
            "output": "",
            "bytes_freed": 0,
        }

        try:
            # Calculate size before removal
            size = await asyncio.to_thread(self._get_dir_size, path)
            step["bytes_freed"] = size

            # Remove the directory
            await asyncio.to_thread(shutil.rmtree, path, ignore_errors=True)

            if not path.exists():
                step["success"] = True
                mb = size / (1024 * 1024)
                step["output"] = f"Removed {path.name} ({mb:.1f} MB)"
            else:
                step["output"] = f"Failed to fully remove {path.name}"

        except Exception as e:
            step["output"] = str(e)

        steps.append(step)
        return step["bytes_freed"] if step["success"] else 0

    def _get_dir_size(self, path: Path) -> int:
        """Get total size of a directory."""
        total = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    try:
                        total += entry.stat().st_size
                    except (OSError, IOError):
                        pass
        except (OSError, IOError):
            pass
        return total

    async def _clean_caches(self, steps: list[dict]) -> int:
        """Clean package manager caches."""
        total_freed = 0

        # npm cache clean
        npm_step = await self._run_cache_clean(
            ["npm", "cache", "clean", "--force"],
            "npm cache clean"
        )
        steps.append(npm_step)
        if npm_step["success"]:
            total_freed += npm_step.get("bytes_freed", 0)

        return total_freed

    async def _run_cache_clean(self, cmd: list[str], action: str) -> dict:
        """Run a cache clean command."""
        step = {
            "action": action,
            "command": " ".join(cmd),
            "success": False,
            "output": "",
            "bytes_freed": 0,
        }

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            step["success"] = result.returncode == 0
            step["output"] = result.stdout or result.stderr or "Cache cleaned"

        except FileNotFoundError:
            step["output"] = f"Command not found: {cmd[0]}"
        except subprocess.TimeoutExpired:
            step["output"] = "Command timed out"
        except Exception as e:
            step["output"] = str(e)

        return step

    async def _kill_process(self, pid: int, name: str) -> dict:
        """Kill a process by PID."""
        step = {
            "action": f"kill {name} (PID: {pid})",
            "success": False,
            "output": "",
        }

        try:
            import signal
            import os

            os.kill(pid, signal.SIGTERM)
            await asyncio.sleep(1)

            # Check if still running
            try:
                os.kill(pid, 0)
                # Still running, force kill
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass  # Process already dead

            step["success"] = True
            step["output"] = f"Process {pid} terminated"

        except Exception as e:
            step["output"] = str(e)

        return step

    def _is_safe_to_clean(self, path: str) -> bool:
        """Check if a path is safe to clean."""
        path_lower = path.lower()

        # Never clean system directories
        unsafe_patterns = [
            "/system", "/windows", "/program files", "/usr", "/bin",
            "/etc", "/var", "/boot", "/lib", "appdata/local/microsoft",
        ]

        for pattern in unsafe_patterns:
            if pattern in path_lower:
                return False

        # Check if it matches safe patterns
        for safe_name in self.SAFE_CLEAN_DIRS:
            clean_name = safe_name.replace("*", "")
            if clean_name in path_lower:
                return True

        return False

    def estimate_risk(self, issue: Issue) -> str:
        """Estimate risk of cleanup operation."""
        if issue.category == IssueCategory.MEMORY:
            return "medium"

        # Disk cleanup is generally low risk if we're careful
        severity = issue.severity.value
        if severity == "critical":
            return "medium"

        return "low"


__all__ = ["CleanupResolver"]
