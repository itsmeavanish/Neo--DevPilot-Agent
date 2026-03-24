"""
Process management tool.

Monitor and control system processes.
"""

import asyncio
import os
import platform
import subprocess
from typing import ClassVar

from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import tool_registry
from jarvis.core.constants import RiskLevel

IS_WINDOWS = platform.system() == "Windows"


@tool_registry.register
class ProcessTool(BaseTool):
    """Monitor and control system processes."""

    name: ClassVar[str] = "process"
    description: ClassVar[str] = (
        "Monitor and control system processes. List running processes, "
        "find processes by name or port, kill processes."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.HIGH
    timeout: ClassVar[int] = 30

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "find", "find_by_port", "kill", "info"],
                "description": "Action to perform",
            },
            "name": {
                "type": "string",
                "description": "Process name to find or filter",
            },
            "pid": {
                "type": "integer",
                "description": "Process ID",
            },
            "port": {
                "type": "integer",
                "description": "Port number to find process using it",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of processes to return",
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["action"],
    }

    async def execute(self, params: dict) -> ToolResult:
        action = params["action"]
        name = params.get("name")
        pid = params.get("pid")
        port = params.get("port")
        limit = params.get("limit", 50)

        try:
            if action == "list":
                return await self._list_processes(name, limit)

            elif action == "find":
                if not name:
                    return ToolResult.failure("Process name is required for find action")
                return await self._find_process(name)

            elif action == "find_by_port":
                if not port:
                    return ToolResult.failure("Port is required for find_by_port action")
                return await self._find_by_port(port)

            elif action == "kill":
                if not pid:
                    return ToolResult.failure("PID is required for kill action")
                return await self._kill_process(pid)

            elif action == "info":
                if not pid:
                    return ToolResult.failure("PID is required for info action")
                return await self._process_info(pid)

            else:
                return ToolResult.failure(f"Unknown action: {action}")

        except Exception as e:
            return ToolResult.failure(f"Process operation failed: {e}")

    async def _list_processes(self, name_filter: str | None, limit: int) -> ToolResult:
        """List running processes."""
        try:
            import psutil
        except ImportError:
            # Fallback to command line
            return await self._list_processes_cli(name_filter, limit)

        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                info = proc.info
                if name_filter and name_filter.lower() not in info['name'].lower():
                    continue
                processes.append({
                    'pid': info['pid'],
                    'name': info['name'],
                    'cpu_percent': round(info['cpu_percent'] or 0, 1),
                    'memory_percent': round(info['memory_percent'] or 0, 1),
                    'status': info['status'],
                })
                if len(processes) >= limit:
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by CPU usage
        processes.sort(key=lambda x: x['cpu_percent'], reverse=True)

        return ToolResult.success(
            processes,
            count=len(processes),
            filtered=bool(name_filter),
        )

    async def _list_processes_cli(self, name_filter: str | None, limit: int) -> ToolResult:
        """List processes using CLI commands."""
        if IS_WINDOWS:
            cmd = ["tasklist", "/FO", "CSV", "/NH"]
        else:
            cmd = ["ps", "aux", "--no-headers"]

        result = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, text=True
        )

        if result.returncode != 0:
            return ToolResult.failure(f"Failed to list processes: {result.stderr}")

        processes = []
        for line in result.stdout.strip().split('\n')[:limit * 2]:
            if IS_WINDOWS:
                # Parse CSV format: "name","pid","session","session#","mem"
                parts = [p.strip('"') for p in line.split(',')]
                if len(parts) >= 2:
                    name = parts[0]
                    pid = parts[1]
                    if name_filter and name_filter.lower() not in name.lower():
                        continue
                    processes.append({'pid': int(pid), 'name': name})
            else:
                parts = line.split()
                if len(parts) >= 11:
                    name = parts[10]
                    pid = parts[1]
                    if name_filter and name_filter.lower() not in name.lower():
                        continue
                    processes.append({
                        'pid': int(pid),
                        'name': name,
                        'cpu_percent': float(parts[2]),
                        'memory_percent': float(parts[3]),
                    })

            if len(processes) >= limit:
                break

        return ToolResult.success(processes, count=len(processes))

    async def _find_process(self, name: str) -> ToolResult:
        """Find processes by name."""
        return await self._list_processes(name, 20)

    async def _find_by_port(self, port: int) -> ToolResult:
        """Find process using a specific port."""
        if IS_WINDOWS:
            cmd = ["netstat", "-ano"]
        else:
            cmd = ["lsof", "-i", f":{port}"]

        result = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, text=True
        )

        if result.returncode != 0:
            return ToolResult.failure(f"Failed to find process: {result.stderr}")

        processes = []
        for line in result.stdout.strip().split('\n'):
            if IS_WINDOWS:
                if f":{port}" in line:
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        if pid.isdigit():
                            processes.append({'pid': int(pid), 'port': port})
            else:
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        processes.append({
                            'pid': int(parts[1]) if parts[1].isdigit() else None,
                            'name': parts[0],
                            'port': port,
                        })

        return ToolResult.success(
            processes,
            port=port,
            count=len(processes),
        )

    async def _kill_process(self, pid: int) -> ToolResult:
        """Kill a process by PID."""
        try:
            import psutil
            proc = psutil.Process(pid)
            proc_name = proc.name()
            proc.terminate()

            # Wait a bit for graceful termination
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                # Force kill
                proc.kill()

            return ToolResult.success(
                f"Killed process {pid} ({proc_name})",
                pid=pid,
                name=proc_name,
            )
        except ImportError:
            # Fallback to command line
            if IS_WINDOWS:
                cmd = ["taskkill", "/PID", str(pid), "/F"]
            else:
                cmd = ["kill", "-9", str(pid)]

            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True
            )

            if result.returncode == 0:
                return ToolResult.success(f"Killed process {pid}", pid=pid)
            else:
                return ToolResult.failure(f"Failed to kill process: {result.stderr}")
        except Exception as e:
            return ToolResult.failure(f"Failed to kill process {pid}: {e}")

    async def _process_info(self, pid: int) -> ToolResult:
        """Get detailed info about a process."""
        try:
            import psutil
            proc = psutil.Process(pid)

            info = {
                'pid': pid,
                'name': proc.name(),
                'status': proc.status(),
                'cpu_percent': proc.cpu_percent(),
                'memory_percent': round(proc.memory_percent(), 2),
                'memory_mb': round(proc.memory_info().rss / 1024 / 1024, 2),
                'create_time': proc.create_time(),
                'cwd': proc.cwd() if hasattr(proc, 'cwd') else None,
                'cmdline': ' '.join(proc.cmdline()) if proc.cmdline() else None,
            }

            return ToolResult.success(info)
        except ImportError:
            return ToolResult.failure("psutil not installed. Install with: pip install psutil")
        except Exception as e:
            return ToolResult.failure(f"Failed to get process info: {e}")


__all__ = ["ProcessTool"]
