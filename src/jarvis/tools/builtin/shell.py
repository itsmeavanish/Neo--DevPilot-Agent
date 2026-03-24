"""
Shell command execution tool.

Provides secure command execution with allowlist validation.
"""

import asyncio
import os
import platform
import shlex
import subprocess
from typing import ClassVar

from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import tool_registry
from jarvis.core.constants import RiskLevel, COMMAND_ALLOWLIST, DEFAULT_COMMAND_TIMEOUT
from jarvis.core.exceptions import CommandNotAllowedError

IS_WINDOWS = platform.system() == "Windows"


@tool_registry.register
class RunCommandTool(BaseTool):
    """Execute shell commands safely."""

    name: ClassVar[str] = "run_command"
    description: ClassVar[str] = (
        "Execute a shell command. Supports common development tools like npm, pip, git, docker. "
        "Commands are validated against an allowlist for security."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.MEDIUM
    timeout: ClassVar[int] = DEFAULT_COMMAND_TIMEOUT

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command (optional)",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 60)",
                "minimum": 1,
                "maximum": 600,
            },
            "shell": {
                "type": "boolean",
                "description": "Run through shell interpreter (default: true for Windows)",
            },
        },
        "required": ["command"],
    }

    # Extended allowlist with common dev tools
    ALLOWLIST = COMMAND_ALLOWLIST | {
        # Additional safe commands
        "tree", "env", "set", "printenv",
        "test", "jest", "pytest", "mocha", "vitest",
        "eslint", "prettier", "tsc", "esbuild", "vite", "webpack",
        "prisma", "drizzle",
    }

    # Patterns that indicate dangerous operations
    DANGEROUS_PATTERNS = [
        "rm -rf /", "rm -rf ~", "rm -rf .",
        "del /s /q c:\\",
        "format c:",
        ":(){:|:&};:",  # Fork bomb
        "> /dev/sda",
        "mkfs.",
        "dd if=",
    ]

    async def execute(self, params: dict) -> ToolResult:
        command = params["command"].strip()
        cwd = params.get("cwd")
        timeout = params.get("timeout", self.timeout)
        shell = params.get("shell", IS_WINDOWS)

        # Validate command
        validation_error = self._validate_command(command)
        if validation_error:
            return ToolResult.failure(validation_error)

        # Prepare working directory
        if cwd:
            cwd = os.path.expanduser(cwd)
            if not os.path.isdir(cwd):
                return ToolResult.failure(f"Directory not found: {cwd}")

        self.logger.info(f"Executing: {command}")

        try:
            result = await asyncio.wait_for(
                self._run_command(command, cwd, shell),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            return ToolResult.failure(
                f"Command timed out after {timeout}s",
                command=command,
                timeout=timeout,
            )
        except Exception as e:
            self.logger.exception(f"Command execution failed: {e}")
            return ToolResult.failure(str(e), command=command)

    def _validate_command(self, command: str) -> str | None:
        """Validate command against security rules."""
        # Check for dangerous patterns
        cmd_lower = command.lower()
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in cmd_lower:
                return f"Dangerous command pattern detected: {pattern}"

        # Extract base command
        parts = shlex.split(command, posix=not IS_WINDOWS) if not IS_WINDOWS else command.split()
        if not parts:
            return "Empty command"

        base_cmd = parts[0].lower()
        # Remove path prefix if present
        base_cmd = os.path.basename(base_cmd)
        # Remove .exe/.cmd extension on Windows
        if IS_WINDOWS:
            for ext in (".exe", ".cmd", ".bat", ".ps1"):
                if base_cmd.endswith(ext):
                    base_cmd = base_cmd[:-len(ext)]

        if base_cmd not in self.ALLOWLIST:
            return f"Command '{base_cmd}' is not in the allowlist. Allowed: {', '.join(sorted(self.ALLOWLIST))}"

        return None

    async def _run_command(
        self,
        command: str,
        cwd: str | None,
        shell: bool,
    ) -> ToolResult:
        """Execute the command in a subprocess."""
        env = self._get_env()

        # Prepare command
        if shell:
            args = command
        else:
            args = shlex.split(command, posix=not IS_WINDOWS)

        # Run in thread to avoid blocking
        def run_sync():
            return subprocess.run(
                args,
                capture_output=True,
                text=True,
                cwd=cwd,
                shell=shell,
                env=env,
                stdin=subprocess.DEVNULL,
            )

        result = await asyncio.to_thread(run_sync)

        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""

        if result.returncode == 0:
            return ToolResult.success(
                stdout or "(no output)",
                exit_code=result.returncode,
                stderr=stderr if stderr else None,
            )
        else:
            return ToolResult.failure(
                stderr or stdout or f"Command failed with exit code {result.returncode}",
                exit_code=result.returncode,
                stdout=stdout,
            )

    def _get_env(self) -> dict[str, str]:
        """Get environment with proper PATH."""
        env = os.environ.copy()

        if IS_WINDOWS:
            # Add common tool paths
            additional_paths = [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\bin"),
                os.path.expandvars(r"%ProgramFiles%\Microsoft VS Code\bin"),
                os.path.expandvars(r"%ProgramFiles%\Git\cmd"),
                os.path.expandvars(r"%ProgramFiles%\nodejs"),
                os.path.expandvars(r"%APPDATA%\npm"),
            ]
            current_path = env.get("PATH", "")
            for p in additional_paths:
                if os.path.exists(p) and p not in current_path:
                    current_path = f"{p};{current_path}"
            env["PATH"] = current_path

        return env


__all__ = ["RunCommandTool"]
