"""
Port monitor for self-healing system.

Detects port conflicts and availability issues.
"""

import asyncio
import socket
from typing import ClassVar

from jarvis.self_heal.monitors.base import BaseMonitor
from jarvis.self_heal.models.issue import Issue, IssueCategory, IssueSeverity


class PortMonitor(BaseMonitor):
    """Monitor for port availability and conflicts."""

    name: ClassVar[str] = "port"
    description: ClassVar[str] = "Monitors port availability and detects conflicts"

    # Ports to monitor
    required_ports: dict[int, str] = {}  # port -> service name

    # Common dev ports
    COMMON_DEV_PORTS = {
        3000: "React/Node dev server",
        3001: "React alt port",
        4200: "Angular dev server",
        5000: "Flask/Python",
        5173: "Vite",
        5432: "PostgreSQL",
        6379: "Redis",
        8000: "JARVIS/FastAPI",
        8080: "HTTP alt/Tomcat",
        8888: "Jupyter",
        11434: "Ollama",
        27017: "MongoDB",
    }

    async def check(self) -> list[Issue]:
        """Check for port issues."""
        issues = []

        # Check required ports
        for port, service in self.required_ports.items():
            is_available = await self._check_port_available(port)
            if not is_available:
                # Port is in use - check if it's the expected service
                process_info = await self._get_port_process(port)

                issues.append(Issue(
                    category=IssueCategory.PORT,
                    severity=IssueSeverity.ERROR,
                    title=f"Port {port} unavailable",
                    description=f"Port {port} needed for {service} is already in use",
                    details={
                        "port": port,
                        "service": service,
                        "blocking_process": process_info,
                    },
                    source=self.name,
                    affected_resource=f"port:{port}",
                    suggested_resolution=f"Kill process using port {port} or use different port",
                    auto_resolvable=True,
                    requires_approval=True,
                ))

        # Check for common port conflicts
        conflicts = await self._detect_port_conflicts()
        for conflict in conflicts:
            issues.append(conflict)

        return issues

    async def _check_port_available(self, port: int, host: str = "127.0.0.1") -> bool:
        """Check if a port is available."""
        def check():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            try:
                sock.bind((host, port))
                sock.close()
                return True
            except (socket.error, OSError):
                return False
            finally:
                try:
                    sock.close()
                except Exception:
                    pass

        return await asyncio.to_thread(check)

    async def _get_port_process(self, port: int) -> dict | None:
        """Get info about process using a port."""
        try:
            import psutil

            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr.port == port:
                    try:
                        proc = psutil.Process(conn.pid)
                        return {
                            "pid": conn.pid,
                            "name": proc.name(),
                            "cmdline": " ".join(proc.cmdline()[:3]),
                        }
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        return {"pid": conn.pid, "name": "unknown"}

        except ImportError:
            pass
        except Exception as e:
            self.logger.debug(f"Error getting port process: {e}")

        return None

    async def _detect_port_conflicts(self) -> list[Issue]:
        """Detect processes fighting over the same port."""
        issues = []

        try:
            import psutil

            # Group connections by port
            port_users: dict[int, list] = {}
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'LISTEN' and conn.laddr.port in self.COMMON_DEV_PORTS:
                    port = conn.laddr.port
                    if port not in port_users:
                        port_users[port] = []
                    port_users[port].append(conn.pid)

            # Check for multiple listeners on same port (shouldn't happen normally)
            for port, pids in port_users.items():
                if len(set(pids)) > 1:
                    issues.append(Issue(
                        category=IssueCategory.PORT,
                        severity=IssueSeverity.WARNING,
                        title=f"Multiple processes on port {port}",
                        description=f"{len(pids)} processes trying to use port {port}",
                        details={
                            "port": port,
                            "service": self.COMMON_DEV_PORTS.get(port, "unknown"),
                            "pids": list(set(pids)),
                        },
                        source=self.name,
                        affected_resource=f"port:{port}",
                    ))

        except ImportError:
            pass
        except Exception as e:
            self.logger.debug(f"Error detecting port conflicts: {e}")

        return issues

    def require_port(self, port: int, service: str) -> None:
        """Mark a port as required."""
        self.required_ports[port] = service

    def release_port(self, port: int) -> None:
        """Remove port from required list."""
        self.required_ports.pop(port, None)

    async def find_available_port(self, start: int = 3000, end: int = 9000) -> int | None:
        """Find an available port in range."""
        for port in range(start, end):
            if await self._check_port_available(port):
                return port
        return None


__all__ = ["PortMonitor"]
