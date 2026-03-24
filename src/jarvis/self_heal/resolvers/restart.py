"""
Restart resolver for crashed/hung processes.

Handles process restart operations.
"""

import asyncio
import subprocess
from typing import ClassVar

from jarvis.self_heal.resolvers.base import BaseResolver
from jarvis.self_heal.models.issue import Issue, IssueCategory


class RestartResolver(BaseResolver):
    """Resolver for process-related issues."""

    name: ClassVar[str] = "restart"
    description: ClassVar[str] = "Restarts crashed or hung processes"
    handles: ClassVar[list[IssueCategory]] = [IssueCategory.PROCESS, IssueCategory.SERVICE]

    # Known services and their restart commands
    RESTART_COMMANDS: ClassVar[dict[str, list[str]]] = {
        # Development servers
        "node": ["npm", "start"],
        "nodemon": ["npx", "nodemon"],
        "python": ["python", "-m", "flask", "run"],
        "uvicorn": ["uvicorn", "main:app", "--reload"],

        # Databases (for dev use)
        "redis": ["redis-server"],
        "postgres": ["pg_ctl", "start"],
    }

    # Processes that are safe to kill
    SAFE_TO_KILL: ClassVar[set[str]] = {
        "node", "nodemon", "python", "npm", "npx",
        "webpack", "vite", "esbuild", "tsc",
    }

    async def _execute(self, issue: Issue) -> tuple[bool, str, list[dict]]:
        """Execute process restart."""
        steps = []
        process_name = issue.affected_resource

        # Step 1: Try to identify and kill the hung process
        if issue.category == IssueCategory.PROCESS:
            pid = issue.details.get("pid")
            if pid and process_name in self.SAFE_TO_KILL:
                kill_step = await self._kill_process(pid, process_name)
                steps.append(kill_step)

                if not kill_step["success"]:
                    return False, kill_step["output"], steps

        # Step 2: Check for restart command in details
        restart_cmd = issue.details.get("restart_command")
        if restart_cmd:
            restart_step = await self._run_command(restart_cmd, "restart service")
            steps.append(restart_step)
            return restart_step["success"], restart_step["output"], steps

        # Step 3: Try known restart command
        if process_name in self.RESTART_COMMANDS:
            cmd = self.RESTART_COMMANDS[process_name]
            restart_step = await self._run_command(cmd, f"restart {process_name}")
            steps.append(restart_step)
            return restart_step["success"], restart_step["output"], steps

        # Step 4: No known restart command
        return False, f"No restart command known for: {process_name}", steps

    async def _kill_process(self, pid: int, name: str) -> dict:
        """Kill a process by PID."""
        step = {
            "action": f"kill process {name} (PID: {pid})",
            "command": f"kill {pid}",
            "success": False,
            "output": "",
        }

        try:
            # Try graceful termination first
            result = await asyncio.to_thread(
                subprocess.run,
                ["taskkill", "/PID", str(pid), "/F"],  # Windows
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                step["success"] = True
                step["output"] = f"Process {pid} terminated"
            else:
                # Try Unix-style kill
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["kill", "-15", str(pid)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                step["success"] = result.returncode == 0
                step["output"] = result.stdout or result.stderr

        except subprocess.TimeoutExpired:
            step["output"] = "Timeout killing process"
        except Exception as e:
            step["output"] = str(e)

        return step

    async def _run_command(self, cmd: list[str], description: str) -> dict:
        """Run a restart command."""
        step = {
            "action": description,
            "command": " ".join(cmd),
            "success": False,
            "output": "",
        }

        try:
            # Start process in background (don't wait for completion)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait briefly to check if it starts successfully
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=5.0
                )
                # If it exits within 5 seconds, check return code
                if process.returncode == 0:
                    step["success"] = True
                    step["output"] = stdout.decode() if stdout else "Started"
                else:
                    step["output"] = stderr.decode() if stderr else "Start failed"
            except asyncio.TimeoutError:
                # Process is still running after 5s - that's good
                step["success"] = True
                step["output"] = f"Process started (PID: {process.pid})"

        except FileNotFoundError:
            step["output"] = f"Command not found: {cmd[0]}"
        except Exception as e:
            step["output"] = str(e)

        return step

    def estimate_risk(self, issue: Issue) -> str:
        """Estimate risk of restart operation."""
        process_name = issue.affected_resource

        if process_name in self.SAFE_TO_KILL:
            return "low"
        elif issue.category == IssueCategory.SERVICE:
            return "medium"
        else:
            return "high"


__all__ = ["RestartResolver"]
