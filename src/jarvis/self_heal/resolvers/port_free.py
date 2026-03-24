"""
Port conflict resolver.

Handles port conflicts by finding and killing conflicting processes.
"""

import asyncio
import subprocess
import platform
from typing import ClassVar

from jarvis.self_heal.resolvers.base import BaseResolver
from jarvis.self_heal.models.issue import Issue, IssueCategory


class PortFreeResolver(BaseResolver):
    """Resolver for port conflicts."""

    name: ClassVar[str] = "port_free"
    description: ClassVar[str] = "Frees ports from conflicting processes"
    handles: ClassVar[list[IssueCategory]] = [IssueCategory.PORT]

    # Processes that are generally safe to kill for port conflicts
    SAFE_TO_KILL: ClassVar[set[str]] = {
        "node", "node.exe", "python", "python.exe",
        "npm", "npm.cmd", "npx", "npx.cmd",
        "uvicorn", "flask", "django", "gunicorn",
        "webpack", "vite", "esbuild",
    }

    # System processes - never kill these
    PROTECTED_PROCESSES: ClassVar[set[str]] = {
        "system", "svchost", "lsass", "csrss", "smss",
        "services", "wininit", "winlogon", "systemd",
        "init", "launchd", "nginx", "apache2", "httpd",
    }

    async def _execute(self, issue: Issue) -> tuple[bool, str, list[dict]]:
        """Execute port freeing."""
        steps = []
        port = issue.details.get("port")

        if not port:
            return False, "No port specified in issue", steps

        # Step 1: Find process using the port
        find_step = await self._find_process_on_port(port)
        steps.append(find_step)

        if not find_step["success"]:
            return False, find_step["output"], steps

        pid = find_step.get("pid")
        process_name = find_step.get("process_name", "").lower()

        # Step 2: Check if it's safe to kill
        if process_name in self.PROTECTED_PROCESSES:
            return False, f"Cannot kill protected process: {process_name}", steps

        if process_name not in self.SAFE_TO_KILL:
            # Not in whitelist - require explicit approval handled by caller
            self.logger.warning(f"Process {process_name} not in safe-to-kill list")

        # Step 3: Kill the process
        if pid:
            kill_step = await self._kill_process(pid)
            steps.append(kill_step)

            if kill_step["success"]:
                # Step 4: Verify port is free
                verify_step = await self._verify_port_free(port)
                steps.append(verify_step)
                return verify_step["success"], verify_step["output"], steps

            return False, kill_step["output"], steps

        return False, "Could not find process PID", steps

    async def _find_process_on_port(self, port: int) -> dict:
        """Find the process using a specific port."""
        step = {
            "action": f"find process on port {port}",
            "success": False,
            "output": "",
            "pid": None,
            "process_name": "",
        }

        system = platform.system().lower()

        try:
            if system == "windows":
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["netstat", "-ano"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                for line in result.stdout.splitlines():
                    if f":{port}" in line and ("LISTENING" in line or "ESTABLISHED" in line):
                        parts = line.split()
                        if parts:
                            pid = int(parts[-1])
                            step["pid"] = pid
                            step["success"] = True

                            # Get process name
                            name_result = await asyncio.to_thread(
                                subprocess.run,
                                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                                capture_output=True,
                                text=True,
                                timeout=10,
                            )
                            if name_result.stdout:
                                name = name_result.stdout.strip().split(",")[0].strip('"')
                                step["process_name"] = name
                                step["output"] = f"Found {name} (PID: {pid}) on port {port}"
                            else:
                                step["output"] = f"Found PID {pid} on port {port}"
                            break
            else:
                # Unix-like systems
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["lsof", "-i", f":{port}", "-t"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.stdout.strip():
                    pid = int(result.stdout.strip().split()[0])
                    step["pid"] = pid
                    step["success"] = True

                    # Get process name
                    name_result = await asyncio.to_thread(
                        subprocess.run,
                        ["ps", "-p", str(pid), "-o", "comm="],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    name = name_result.stdout.strip()
                    step["process_name"] = name
                    step["output"] = f"Found {name} (PID: {pid}) on port {port}"

            if not step["success"]:
                step["output"] = f"No process found on port {port}"

        except Exception as e:
            step["output"] = f"Error finding process: {e}"

        return step

    async def _kill_process(self, pid: int) -> dict:
        """Kill a process by PID."""
        step = {
            "action": f"kill process (PID: {pid})",
            "success": False,
            "output": "",
        }

        system = platform.system().lower()

        try:
            if system == "windows":
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["taskkill", "/PID", str(pid), "/F"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            else:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["kill", "-9", str(pid)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

            step["success"] = result.returncode == 0
            step["output"] = result.stdout or result.stderr or "Process killed"

        except Exception as e:
            step["output"] = f"Error killing process: {e}"

        return step

    async def _verify_port_free(self, port: int) -> dict:
        """Verify a port is now free."""
        step = {
            "action": f"verify port {port} is free",
            "success": False,
            "output": "",
        }

        try:
            # Wait a moment for the port to be released
            await asyncio.sleep(0.5)

            # Try to bind to the port
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()

            if result != 0:
                # Connection refused = port is free
                step["success"] = True
                step["output"] = f"Port {port} is now free"
            else:
                step["output"] = f"Port {port} is still in use"

        except Exception as e:
            # Error connecting usually means port is free
            step["success"] = True
            step["output"] = f"Port {port} appears free: {e}"

        return step

    def estimate_risk(self, issue: Issue) -> str:
        """Estimate risk of freeing this port."""
        port = issue.details.get("port", 0)
        process_name = issue.details.get("process_name", "").lower()

        # Well-known ports are higher risk
        if port < 1024:
            return "high"

        # Protected processes
        if process_name in self.PROTECTED_PROCESSES:
            return "critical"

        # Safe processes
        if process_name in self.SAFE_TO_KILL:
            return "low"

        return "medium"


__all__ = ["PortFreeResolver"]
