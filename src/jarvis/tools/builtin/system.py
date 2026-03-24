"""
System information tool.

Get system stats, environment info, and health metrics.
"""

import asyncio
import os
import platform
import shutil
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import tool_registry
from jarvis.core.constants import RiskLevel


@tool_registry.register
class SystemInfoTool(BaseTool):
    """Get system information and health metrics."""

    name: ClassVar[str] = "system_info"
    description: ClassVar[str] = (
        "Get system information including CPU, memory, disk usage, "
        "environment variables, and runtime info. Useful for debugging "
        "and monitoring."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.LOW
    timeout: ClassVar[int] = 30

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "info_type": {
                "type": "string",
                "enum": [
                    "all", "cpu", "memory", "disk", "network",
                    "os", "env", "runtime", "health"
                ],
                "description": "Type of information to retrieve (default: all)",
            },
            "path": {
                "type": "string",
                "description": "Path for disk info (default: current drive)",
            },
            "env_var": {
                "type": "string",
                "description": "Specific environment variable to get",
            },
        },
    }

    async def execute(self, params: dict) -> ToolResult:
        info_type = params.get("info_type", "all")
        path = params.get("path")
        env_var = params.get("env_var")

        try:
            if info_type == "all":
                return await self._get_all_info()
            elif info_type == "cpu":
                return await self._get_cpu_info()
            elif info_type == "memory":
                return await self._get_memory_info()
            elif info_type == "disk":
                return await self._get_disk_info(path)
            elif info_type == "network":
                return await self._get_network_info()
            elif info_type == "os":
                return await self._get_os_info()
            elif info_type == "env":
                return self._get_env_info(env_var)
            elif info_type == "runtime":
                return self._get_runtime_info()
            elif info_type == "health":
                return await self._get_health_info()
            else:
                return ToolResult.failure(f"Unknown info type: {info_type}")

        except Exception as e:
            return ToolResult.failure(f"Failed to get system info: {e}")

    async def _get_all_info(self) -> ToolResult:
        """Get combined system information."""
        info = {
            "os": self._get_basic_os_info(),
            "runtime": self._get_basic_runtime_info(),
        }

        # Try to add detailed info if psutil is available
        try:
            import psutil

            info["cpu"] = {
                "cores_physical": psutil.cpu_count(logical=False),
                "cores_logical": psutil.cpu_count(logical=True),
                "usage_percent": psutil.cpu_percent(interval=0.1),
            }

            mem = psutil.virtual_memory()
            info["memory"] = {
                "total_gb": round(mem.total / 1024 / 1024 / 1024, 2),
                "available_gb": round(mem.available / 1024 / 1024 / 1024, 2),
                "used_percent": mem.percent,
            }

            disk = psutil.disk_usage(Path.cwd().anchor)
            info["disk"] = {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "used_percent": disk.percent,
            }

        except ImportError:
            # Basic disk info without psutil
            total, used, free = shutil.disk_usage(Path.cwd())
            info["disk"] = {
                "total_gb": round(total / 1024 / 1024 / 1024, 2),
                "free_gb": round(free / 1024 / 1024 / 1024, 2),
                "used_percent": round(used / total * 100, 1),
            }

        return ToolResult.success(info)

    async def _get_cpu_info(self) -> ToolResult:
        """Get CPU information."""
        try:
            import psutil

            # Get CPU times for usage calculation
            cpu_percent = psutil.cpu_percent(interval=1, percpu=True)

            info = {
                "cores_physical": psutil.cpu_count(logical=False),
                "cores_logical": psutil.cpu_count(logical=True),
                "usage_percent_total": round(sum(cpu_percent) / len(cpu_percent), 1),
                "usage_percent_per_core": cpu_percent,
                "frequency_mhz": None,
            }

            # Try to get frequency
            try:
                freq = psutil.cpu_freq()
                if freq:
                    info["frequency_mhz"] = {
                        "current": round(freq.current, 0),
                        "max": round(freq.max, 0) if freq.max else None,
                    }
            except Exception:
                pass

            return ToolResult.success(info)

        except ImportError:
            return ToolResult.success({
                "cores_logical": os.cpu_count(),
                "note": "Install psutil for detailed CPU info",
            })

    async def _get_memory_info(self) -> ToolResult:
        """Get memory information."""
        try:
            import psutil

            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            info = {
                "ram": {
                    "total_gb": round(mem.total / 1024 / 1024 / 1024, 2),
                    "available_gb": round(mem.available / 1024 / 1024 / 1024, 2),
                    "used_gb": round(mem.used / 1024 / 1024 / 1024, 2),
                    "used_percent": mem.percent,
                },
                "swap": {
                    "total_gb": round(swap.total / 1024 / 1024 / 1024, 2),
                    "used_gb": round(swap.used / 1024 / 1024 / 1024, 2),
                    "used_percent": swap.percent,
                },
            }

            return ToolResult.success(info)

        except ImportError:
            return ToolResult.failure("psutil not installed. Install with: pip install psutil")

    async def _get_disk_info(self, path: str | None) -> ToolResult:
        """Get disk information."""
        target = Path(path) if path else Path.cwd()
        target = target.resolve()

        try:
            import psutil

            partitions = []
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total_gb": round(usage.total / 1024 / 1024 / 1024, 2),
                        "free_gb": round(usage.free / 1024 / 1024 / 1024, 2),
                        "used_percent": usage.percent,
                    })
                except Exception:
                    continue

            return ToolResult.success({
                "partitions": partitions,
                "current_path": str(target),
            })

        except ImportError:
            total, used, free = shutil.disk_usage(target.anchor)
            return ToolResult.success({
                "path": str(target),
                "total_gb": round(total / 1024 / 1024 / 1024, 2),
                "free_gb": round(free / 1024 / 1024 / 1024, 2),
                "used_percent": round(used / total * 100, 1),
            })

    async def _get_network_info(self) -> ToolResult:
        """Get network information."""
        try:
            import psutil

            interfaces = []
            for name, addrs in psutil.net_if_addrs().items():
                interface = {"name": name, "addresses": []}
                for addr in addrs:
                    if addr.family.name == "AF_INET":
                        interface["addresses"].append({
                            "type": "ipv4",
                            "address": addr.address,
                        })
                    elif addr.family.name == "AF_INET6":
                        interface["addresses"].append({
                            "type": "ipv6",
                            "address": addr.address,
                        })
                if interface["addresses"]:
                    interfaces.append(interface)

            # Get connections count
            try:
                connections = len(psutil.net_connections())
            except Exception:
                connections = None

            return ToolResult.success({
                "interfaces": interfaces,
                "active_connections": connections,
            })

        except ImportError:
            return ToolResult.failure("psutil not installed. Install with: pip install psutil")

    async def _get_os_info(self) -> ToolResult:
        """Get OS information."""
        return ToolResult.success(self._get_basic_os_info())

    def _get_basic_os_info(self) -> dict:
        """Get basic OS info."""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
        }

    def _get_env_info(self, env_var: str | None) -> ToolResult:
        """Get environment variables."""
        if env_var:
            value = os.environ.get(env_var)
            if value is None:
                return ToolResult.failure(f"Environment variable not found: {env_var}")
            return ToolResult.success({env_var: value})

        # Return safe subset of environment
        safe_vars = {
            "PATH", "HOME", "USER", "USERNAME", "SHELL", "TERM",
            "LANG", "LC_ALL", "TZ", "PWD", "OLDPWD",
            "NODE_ENV", "PYTHON", "PYTHONPATH", "VIRTUAL_ENV",
            "GOPATH", "GOROOT", "JAVA_HOME",
            "EDITOR", "VISUAL",
        }

        env = {k: v for k, v in os.environ.items() if k in safe_vars}
        return ToolResult.success(env)

    def _get_runtime_info(self) -> ToolResult:
        """Get runtime information."""
        return ToolResult.success(self._get_basic_runtime_info())

    def _get_basic_runtime_info(self) -> dict:
        """Get basic runtime info."""
        import sys
        return {
            "python_version": sys.version,
            "python_executable": sys.executable,
            "cwd": str(Path.cwd()),
            "pid": os.getpid(),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    async def _get_health_info(self) -> ToolResult:
        """Get system health metrics."""
        health = {
            "status": "healthy",
            "checks": {},
        }

        # Check disk space
        try:
            total, used, free = shutil.disk_usage(Path.cwd().anchor)
            disk_percent = used / total * 100
            health["checks"]["disk"] = {
                "status": "warning" if disk_percent > 90 else "ok",
                "used_percent": round(disk_percent, 1),
            }
            if disk_percent > 90:
                health["status"] = "warning"
        except Exception as e:
            health["checks"]["disk"] = {"status": "error", "error": str(e)}

        # Check memory
        try:
            import psutil
            mem = psutil.virtual_memory()
            health["checks"]["memory"] = {
                "status": "warning" if mem.percent > 90 else "ok",
                "used_percent": mem.percent,
            }
            if mem.percent > 90:
                health["status"] = "warning"
        except ImportError:
            health["checks"]["memory"] = {"status": "unknown", "note": "psutil not installed"}

        # Check CPU
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            health["checks"]["cpu"] = {
                "status": "warning" if cpu > 90 else "ok",
                "used_percent": cpu,
            }
            if cpu > 90:
                health["status"] = "warning"
        except ImportError:
            health["checks"]["cpu"] = {"status": "unknown", "note": "psutil not installed"}

        return ToolResult.success(health)


__all__ = ["SystemInfoTool"]
