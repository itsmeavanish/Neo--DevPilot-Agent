"""
Git operations tool.

Execute common git commands safely.
"""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import ClassVar

from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import tool_registry
from jarvis.core.constants import RiskLevel


@tool_registry.register
class GitTool(BaseTool):
    """Execute git operations."""

    name: ClassVar[str] = "git"
    description: ClassVar[str] = (
        "Execute git operations like status, diff, log, commit, push, pull. "
        "Supports common git workflows for version control."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.MEDIUM
    timeout: ClassVar[int] = 60

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "status", "diff", "log", "show", "branch", "checkout",
                    "add", "commit", "push", "pull", "fetch",
                    "stash", "stash_pop", "stash_list",
                    "reset", "merge", "rebase",
                    "remote", "clone", "init",
                ],
                "description": "Git operation to perform",
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Additional arguments for the git command",
            },
            "cwd": {
                "type": "string",
                "description": "Repository directory",
            },
            "message": {
                "type": "string",
                "description": "Commit message (for commit operation)",
            },
        },
        "required": ["operation"],
    }

    # Operations that are read-only
    SAFE_OPERATIONS = {"status", "diff", "log", "show", "branch", "remote", "stash_list"}

    # Operations that require extra caution
    DANGEROUS_OPERATIONS = {"reset", "rebase", "push"}

    async def execute(self, params: dict) -> ToolResult:
        operation = params["operation"]
        args = params.get("args", [])
        cwd = params.get("cwd")
        message = params.get("message")

        # Validate dangerous operations
        if operation in self.DANGEROUS_OPERATIONS:
            danger_check = self._check_dangerous_args(operation, args)
            if danger_check:
                return ToolResult.failure(danger_check)

        # Build command
        cmd = self._build_command(operation, args, message)
        if isinstance(cmd, ToolResult):
            return cmd  # Error occurred

        # Resolve working directory
        work_dir = Path(cwd).expanduser().resolve() if cwd else Path.cwd()
        if not work_dir.exists():
            return ToolResult.failure(f"Directory not found: {work_dir}")

        # Check if it's a git repo (for non-init/clone operations)
        if operation not in ("init", "clone"):
            if not (work_dir / ".git").exists() and not self._find_git_root(work_dir):
                return ToolResult.failure(f"Not a git repository: {work_dir}")

        self.logger.info(f"Git {operation}: {' '.join(cmd)}")

        try:
            result = await asyncio.wait_for(
                self._run_git(cmd, str(work_dir)),
                timeout=self.timeout,
            )
            return result
        except asyncio.TimeoutError:
            return ToolResult.failure(f"Git operation timed out after {self.timeout}s")
        except Exception as e:
            return ToolResult.failure(f"Git operation failed: {e}")

    def _build_command(self, operation: str, args: list[str], message: str | None) -> list[str] | ToolResult:
        """Build the git command."""
        cmd = ["git"]

        if operation == "stash_pop":
            cmd.extend(["stash", "pop"])
        elif operation == "stash_list":
            cmd.extend(["stash", "list"])
        elif operation == "commit":
            if not message:
                return ToolResult.failure("Commit message is required")
            cmd.extend(["commit", "-m", message])
        else:
            cmd.append(operation)

        cmd.extend(args)
        return cmd

    def _check_dangerous_args(self, operation: str, args: list[str]) -> str | None:
        """Check for dangerous argument combinations."""
        args_str = " ".join(args).lower()

        if operation == "reset":
            if "--hard" in args_str:
                return "Hard reset requires explicit approval. This will discard uncommitted changes."

        if operation == "push":
            if "--force" in args_str or "-f" in args:
                return "Force push requires explicit approval. This can overwrite remote history."
            if "main" in args_str or "master" in args_str:
                if "--force" in args_str or "-f" in args:
                    return "Force push to main/master is blocked."

        if operation == "rebase":
            # Rebase is generally okay, but warn about interactive
            pass

        return None

    def _find_git_root(self, path: Path) -> Path | None:
        """Find the git root directory."""
        current = path
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return None

    async def _run_git(self, cmd: list[str], cwd: str) -> ToolResult:
        """Execute git command."""
        def run_sync():
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
            )

        result = await asyncio.to_thread(run_sync)

        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""

        if result.returncode == 0:
            return ToolResult.success(
                stdout or "(no output)",
                exit_code=result.returncode,
            )
        else:
            # Some git commands write to stderr even on success
            output = stderr or stdout
            return ToolResult.failure(
                output or f"Git command failed with exit code {result.returncode}",
                exit_code=result.returncode,
            )


__all__ = ["GitTool"]
