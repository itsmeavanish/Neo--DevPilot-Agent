"""
Docker control tool.

Manage Docker containers and images.
"""

import asyncio
import subprocess
from typing import ClassVar

from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import tool_registry
from jarvis.core.constants import RiskLevel


@tool_registry.register
class DockerTool(BaseTool):
    """Control Docker containers and images."""

    name: ClassVar[str] = "docker"
    description: ClassVar[str] = (
        "Manage Docker containers and images. List, run, stop, remove containers. "
        "Build and manage images. View logs."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.MEDIUM
    timeout: ClassVar[int] = 120

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "ps", "images", "logs", "inspect",
                    "run", "start", "stop", "restart", "rm",
                    "build", "pull", "push", "tag",
                    "exec", "cp",
                    "network_ls", "volume_ls",
                    "compose_up", "compose_down", "compose_ps",
                ],
                "description": "Docker action to perform",
            },
            "target": {
                "type": "string",
                "description": "Container name/ID, image name, or path",
            },
            "command": {
                "type": "string",
                "description": "Command to execute (for run/exec)",
            },
            "options": {
                "type": "object",
                "description": "Additional options",
                "properties": {
                    "all": {"type": "boolean", "description": "Show all (for ps)"},
                    "follow": {"type": "boolean", "description": "Follow logs"},
                    "tail": {"type": "integer", "description": "Lines of logs to show"},
                    "detach": {"type": "boolean", "description": "Run in background"},
                    "rm": {"type": "boolean", "description": "Remove after exit"},
                    "port": {"type": "string", "description": "Port mapping (host:container)"},
                    "env": {"type": "array", "items": {"type": "string"}, "description": "Environment variables"},
                    "volume": {"type": "array", "items": {"type": "string"}, "description": "Volume mounts"},
                    "name": {"type": "string", "description": "Container name"},
                    "tag": {"type": "string", "description": "Image tag"},
                    "file": {"type": "string", "description": "Dockerfile path or compose file"},
                },
            },
        },
        "required": ["action"],
    }

    async def execute(self, params: dict) -> ToolResult:
        action = params["action"]
        target = params.get("target")
        command = params.get("command")
        options = params.get("options", {})

        # Check if Docker is available
        if not await self._docker_available():
            return ToolResult.failure(
                "Docker is not available. Make sure Docker Desktop is running."
            )

        # Build command
        cmd = self._build_command(action, target, command, options)
        if isinstance(cmd, ToolResult):
            return cmd  # Error occurred

        self.logger.info(f"Docker: {' '.join(cmd)}")

        # Determine timeout based on action
        timeout = self.timeout
        if action in ("build", "pull", "push", "compose_up"):
            timeout = 300  # 5 minutes for long operations

        try:
            result = await asyncio.wait_for(
                self._run_docker(cmd),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            return ToolResult.failure(f"Docker operation timed out after {timeout}s")
        except Exception as e:
            return ToolResult.failure(f"Docker operation failed: {e}")

    def _build_command(self, action: str, target: str | None, command: str | None, options: dict) -> list[str] | ToolResult:
        """Build the docker command."""
        cmd = ["docker"]

        # Handle compose commands
        if action.startswith("compose_"):
            compose_action = action.replace("compose_", "")
            cmd.extend(["compose"])
            if options.get("file"):
                cmd.extend(["-f", options["file"]])
            cmd.append(compose_action)
            if compose_action == "up" and options.get("detach", True):
                cmd.append("-d")
            return cmd

        # Handle network/volume commands
        if action == "network_ls":
            return ["docker", "network", "ls"]
        if action == "volume_ls":
            return ["docker", "volume", "ls"]

        # Standard docker commands
        cmd.append(action)

        # Add options based on action
        if action == "ps":
            if options.get("all"):
                cmd.append("-a")

        elif action == "logs":
            if not target:
                return ToolResult.failure("Container name/ID is required for logs")
            if options.get("follow"):
                cmd.append("-f")
            if options.get("tail"):
                cmd.extend(["--tail", str(options["tail"])])
            cmd.append(target)

        elif action == "run":
            if not target:
                return ToolResult.failure("Image name is required for run")
            if options.get("detach"):
                cmd.append("-d")
            if options.get("rm"):
                cmd.append("--rm")
            if options.get("name"):
                cmd.extend(["--name", options["name"]])
            if options.get("port"):
                cmd.extend(["-p", options["port"]])
            for env in options.get("env", []):
                cmd.extend(["-e", env])
            for vol in options.get("volume", []):
                cmd.extend(["-v", vol])
            cmd.append(target)
            if command:
                cmd.extend(command.split())

        elif action == "exec":
            if not target:
                return ToolResult.failure("Container name/ID is required for exec")
            if not command:
                return ToolResult.failure("Command is required for exec")
            cmd.extend(["-it", target])
            cmd.extend(command.split())

        elif action == "build":
            if options.get("tag"):
                cmd.extend(["-t", options["tag"]])
            if options.get("file"):
                cmd.extend(["-f", options["file"]])
            cmd.append(target or ".")

        elif action in ("start", "stop", "restart", "rm", "inspect"):
            if not target:
                return ToolResult.failure(f"Container name/ID is required for {action}")
            if action == "rm" and options.get("force"):
                cmd.append("-f")
            cmd.append(target)

        elif action in ("pull", "push"):
            if not target:
                return ToolResult.failure(f"Image name is required for {action}")
            cmd.append(target)

        elif action == "tag":
            if not target:
                return ToolResult.failure("Source image is required for tag")
            if not options.get("tag"):
                return ToolResult.failure("Target tag is required")
            cmd.extend([target, options["tag"]])

        elif action == "images":
            if options.get("all"):
                cmd.append("-a")

        else:
            if target:
                cmd.append(target)

        return cmd

    async def _docker_available(self) -> bool:
        """Check if Docker daemon is available."""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["docker", "info"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    async def _run_docker(self, cmd: list[str]) -> ToolResult:
        """Execute docker command."""
        def run_sync():
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
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
            return ToolResult.failure(
                stderr or stdout or f"Docker command failed with exit code {result.returncode}",
                exit_code=result.returncode,
            )


__all__ = ["DockerTool"]
