"""
Device models for multi-device orchestration.

Defines device representation, capabilities, and status tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class DeviceType(Enum):
    """Types of devices that can be orchestrated."""
    DESKTOP = "desktop"
    LAPTOP = "laptop"
    SERVER = "server"
    MOBILE = "mobile"
    CONTAINER = "container"
    VM = "vm"
    REMOTE = "remote"


class DeviceStatus(Enum):
    """Device connection and availability status."""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"


class DeviceRole(Enum):
    """Role of device in the orchestration cluster."""
    CONTROLLER = "controller"  # Main orchestrator
    WORKER = "worker"          # Executes tasks
    HYBRID = "hybrid"          # Both controller and worker


@dataclass
class DeviceCapabilities:
    """
    Capabilities and resources available on a device.
    """
    # Tools available
    tools: list[str] = field(default_factory=list)

    # Runtime environments
    has_python: bool = True
    python_version: str | None = None
    has_node: bool = False
    node_version: str | None = None
    has_docker: bool = False
    has_git: bool = True

    # IDEs available
    has_vscode: bool = False
    has_cursor: bool = False

    # System resources
    cpu_cores: int = 1
    memory_gb: float = 1.0
    disk_gb: float = 10.0

    # Network
    can_access_internet: bool = True
    allowed_hosts: list[str] = field(default_factory=list)

    # Permissions
    can_execute_shell: bool = True
    can_write_files: bool = True
    can_install_packages: bool = False
    max_concurrent_tasks: int = 4

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tools": self.tools,
            "has_python": self.has_python,
            "python_version": self.python_version,
            "has_node": self.has_node,
            "node_version": self.node_version,
            "has_docker": self.has_docker,
            "has_git": self.has_git,
            "has_vscode": self.has_vscode,
            "has_cursor": self.has_cursor,
            "cpu_cores": self.cpu_cores,
            "memory_gb": self.memory_gb,
            "disk_gb": self.disk_gb,
            "can_access_internet": self.can_access_internet,
            "allowed_hosts": self.allowed_hosts,
            "can_execute_shell": self.can_execute_shell,
            "can_write_files": self.can_write_files,
            "can_install_packages": self.can_install_packages,
            "max_concurrent_tasks": self.max_concurrent_tasks,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeviceCapabilities":
        """Create from dictionary."""
        return cls(
            tools=data.get("tools", []),
            has_python=data.get("has_python", True),
            python_version=data.get("python_version"),
            has_node=data.get("has_node", False),
            node_version=data.get("node_version"),
            has_docker=data.get("has_docker", False),
            has_git=data.get("has_git", True),
            has_vscode=data.get("has_vscode", False),
            has_cursor=data.get("has_cursor", False),
            cpu_cores=data.get("cpu_cores", 1),
            memory_gb=data.get("memory_gb", 1.0),
            disk_gb=data.get("disk_gb", 10.0),
            can_access_internet=data.get("can_access_internet", True),
            allowed_hosts=data.get("allowed_hosts", []),
            can_execute_shell=data.get("can_execute_shell", True),
            can_write_files=data.get("can_write_files", True),
            can_install_packages=data.get("can_install_packages", False),
            max_concurrent_tasks=data.get("max_concurrent_tasks", 4),
        )


@dataclass
class DeviceMetrics:
    """Real-time metrics from a device."""
    cpu_usage: float = 0.0        # 0-100%
    memory_usage: float = 0.0     # 0-100%
    disk_usage: float = 0.0       # 0-100%
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    last_heartbeat: datetime | None = None
    latency_ms: float = 0.0       # Network latency

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "disk_usage": self.disk_usage,
            "active_tasks": self.active_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "latency_ms": self.latency_ms,
        }


@dataclass
class Device:
    """
    Represents a device in the orchestration network.
    """
    id: str = field(default_factory=lambda: str(uuid4())[:12])
    name: str = "unnamed"
    device_type: DeviceType = DeviceType.DESKTOP
    role: DeviceRole = DeviceRole.WORKER
    status: DeviceStatus = DeviceStatus.OFFLINE

    # Connection info
    host: str = "localhost"
    port: int = 8765
    api_key: str | None = None

    # Device details
    platform: str = "unknown"          # windows, linux, darwin
    hostname: str = "unknown"
    working_directory: str | None = None

    # Capabilities and metrics
    capabilities: DeviceCapabilities = field(default_factory=DeviceCapabilities)
    metrics: DeviceMetrics = field(default_factory=DeviceMetrics)

    # Timestamps
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime | None = None
    connected_at: datetime | None = None

    # Tags for filtering/grouping
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate device after initialization."""
        if isinstance(self.device_type, str):
            self.device_type = DeviceType(self.device_type)
        if isinstance(self.role, str):
            self.role = DeviceRole(self.role)
        if isinstance(self.status, str):
            self.status = DeviceStatus(self.status)

    @property
    def is_available(self) -> bool:
        """Check if device is available for tasks."""
        if self.status != DeviceStatus.ONLINE:
            return False
        if self.metrics.active_tasks >= self.capabilities.max_concurrent_tasks:
            return False
        return True

    @property
    def address(self) -> str:
        """Get device address for connection."""
        return f"{self.host}:{self.port}"

    @property
    def ws_url(self) -> str:
        """Get WebSocket URL for device."""
        return f"ws://{self.host}:{self.port}/ws"

    @property
    def api_url(self) -> str:
        """Get API URL for device."""
        return f"http://{self.host}:{self.port}/api/v1"

    def can_execute(self, tool_name: str) -> bool:
        """Check if device can execute a specific tool."""
        if not self.is_available:
            return False
        if self.capabilities.tools and tool_name not in self.capabilities.tools:
            return False
        return True

    def update_heartbeat(self) -> None:
        """Update last seen timestamp."""
        self.last_seen = datetime.utcnow()
        self.metrics.last_heartbeat = datetime.utcnow()

    def set_online(self) -> None:
        """Mark device as online."""
        self.status = DeviceStatus.ONLINE
        self.connected_at = datetime.utcnow()
        self.update_heartbeat()

    def set_offline(self) -> None:
        """Mark device as offline."""
        self.status = DeviceStatus.OFFLINE
        self.connected_at = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "device_type": self.device_type.value,
            "role": self.role.value,
            "status": self.status.value,
            "host": self.host,
            "port": self.port,
            "platform": self.platform,
            "hostname": self.hostname,
            "working_directory": self.working_directory,
            "capabilities": self.capabilities.to_dict(),
            "metrics": self.metrics.to_dict(),
            "registered_at": self.registered_at.isoformat(),
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "tags": self.tags,
            "metadata": self.metadata,
            "is_available": self.is_available,
            "address": self.address,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Device":
        """Create device from dictionary."""
        caps = data.get("capabilities", {})
        if isinstance(caps, dict):
            caps = DeviceCapabilities.from_dict(caps)

        return cls(
            id=data.get("id", str(uuid4())[:12]),
            name=data.get("name", "unnamed"),
            device_type=DeviceType(data.get("device_type", "desktop")),
            role=DeviceRole(data.get("role", "worker")),
            status=DeviceStatus(data.get("status", "offline")),
            host=data.get("host", "localhost"),
            port=data.get("port", 8765),
            api_key=data.get("api_key"),
            platform=data.get("platform", "unknown"),
            hostname=data.get("hostname", "unknown"),
            working_directory=data.get("working_directory"),
            capabilities=caps,
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class DeviceTask:
    """
    A task assigned to a device.
    """
    id: str = field(default_factory=lambda: str(uuid4())[:12])
    device_id: str = ""
    tool_name: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    # Status
    status: str = "pending"  # pending, running, completed, failed, cancelled
    priority: int = 5        # 1 (highest) to 10 (lowest)

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    timeout_seconds: int = 300

    # Results
    result: Any = None
    error: str | None = None
    output: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "device_id": self.device_id,
            "tool_name": self.tool_name,
            "params": self.params,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "timeout_seconds": self.timeout_seconds,
            "result": self.result,
            "error": self.error,
            "output": self.output,
        }


__all__ = [
    "DeviceType",
    "DeviceStatus",
    "DeviceRole",
    "DeviceCapabilities",
    "DeviceMetrics",
    "Device",
    "DeviceTask",
]
