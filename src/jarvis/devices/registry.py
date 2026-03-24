"""
Device registry for managing connected devices.

Handles device registration, discovery, health tracking, and selection.
"""

import asyncio
import platform
import os
from datetime import datetime, timedelta
from typing import Callable, Awaitable

from jarvis.core.logging import get_logger
from jarvis.devices.models.device import (
    Device, DeviceStatus, DeviceType, DeviceRole,
    DeviceCapabilities, DeviceMetrics, DeviceTask,
)

logger = get_logger("jarvis.devices.registry")


class DeviceRegistry:
    """
    Central registry for all devices in the orchestration network.

    Handles:
    - Device registration and deregistration
    - Health monitoring and heartbeat tracking
    - Device discovery (local and network)
    - Device selection for task routing
    """

    def __init__(self):
        self.devices: dict[str, Device] = {}
        self.local_device: Device | None = None

        # Pending tasks by device
        self.task_queue: dict[str, list[DeviceTask]] = {}

        # Settings
        self.heartbeat_timeout = timedelta(seconds=30)
        self.discovery_enabled = True

        # Callbacks
        self._on_device_connected: Callable[[Device], Awaitable[None]] | None = None
        self._on_device_disconnected: Callable[[Device], Awaitable[None]] | None = None

        # Background tasks
        self._heartbeat_task: asyncio.Task | None = None

        # Initialize local device
        self._init_local_device()

    def _init_local_device(self) -> None:
        """Initialize the local device entry."""
        self.local_device = Device(
            id="local",
            name=platform.node() or "local",
            device_type=self._detect_device_type(),
            role=DeviceRole.HYBRID,
            status=DeviceStatus.ONLINE,
            host="localhost",
            port=8000,
            platform=platform.system().lower(),
            hostname=platform.node(),
            working_directory=os.getcwd(),
            capabilities=self._detect_capabilities(),
        )
        self.local_device.set_online()
        self.devices["local"] = self.local_device

    def _detect_device_type(self) -> DeviceType:
        """Detect the type of local device."""
        system = platform.system().lower()

        # Check for container/VM
        if os.path.exists("/.dockerenv"):
            return DeviceType.CONTAINER

        # Check battery for laptop detection
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery is not None:
                return DeviceType.LAPTOP
        except (ImportError, Exception):
            pass

        if system == "linux":
            # Check for server indicators
            if os.path.exists("/etc/server-release"):
                return DeviceType.SERVER

        return DeviceType.DESKTOP

    def _detect_capabilities(self) -> DeviceCapabilities:
        """Detect capabilities of local device."""
        import shutil
        import subprocess

        caps = DeviceCapabilities()

        # Python
        caps.has_python = True
        caps.python_version = platform.python_version()

        # Node.js
        if shutil.which("node"):
            caps.has_node = True
            try:
                result = subprocess.run(
                    ["node", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                caps.node_version = result.stdout.strip()
            except Exception:
                pass

        # Docker
        caps.has_docker = shutil.which("docker") is not None

        # Git
        caps.has_git = shutil.which("git") is not None

        # VS Code
        caps.has_vscode = shutil.which("code") is not None

        # Cursor
        caps.has_cursor = shutil.which("cursor") is not None

        # System resources
        try:
            import psutil
            caps.cpu_cores = psutil.cpu_count() or 1
            caps.memory_gb = round(psutil.virtual_memory().total / (1024**3), 1)
            caps.disk_gb = round(psutil.disk_usage("/").total / (1024**3), 1)
        except ImportError:
            pass

        return caps

    # ═══════════════════════════════════════════════════════════════
    # Device Registration
    # ═══════════════════════════════════════════════════════════════

    def register(self, device: Device) -> bool:
        """
        Register a device with the registry.

        Args:
            device: Device to register

        Returns:
            True if registered successfully
        """
        if device.id in self.devices:
            logger.warning(f"Device {device.id} already registered, updating")

        self.devices[device.id] = device
        self.task_queue[device.id] = []

        logger.info(f"Registered device: {device.name} ({device.id})")
        return True

    def unregister(self, device_id: str) -> bool:
        """
        Unregister a device from the registry.

        Args:
            device_id: ID of device to remove

        Returns:
            True if removed, False if not found
        """
        if device_id == "local":
            logger.warning("Cannot unregister local device")
            return False

        if device_id in self.devices:
            device = self.devices.pop(device_id)
            self.task_queue.pop(device_id, None)
            logger.info(f"Unregistered device: {device.name} ({device_id})")
            return True

        return False

    def get(self, device_id: str) -> Device | None:
        """Get device by ID."""
        return self.devices.get(device_id)

    def get_all(self) -> list[Device]:
        """Get all registered devices."""
        return list(self.devices.values())

    def get_online(self) -> list[Device]:
        """Get all online devices."""
        return [d for d in self.devices.values() if d.status == DeviceStatus.ONLINE]

    def get_available(self) -> list[Device]:
        """Get all available devices (online and not busy)."""
        return [d for d in self.devices.values() if d.is_available]

    # ═══════════════════════════════════════════════════════════════
    # Device Selection
    # ═══════════════════════════════════════════════════════════════

    def select_for_tool(self, tool_name: str) -> Device | None:
        """
        Select the best device for executing a tool.

        Selection criteria:
        1. Device must be available
        2. Device must support the tool
        3. Prefer device with lowest load
        4. Prefer local device if tied

        Args:
            tool_name: Name of tool to execute

        Returns:
            Best device or None if none available
        """
        candidates = []

        for device in self.get_available():
            if device.can_execute(tool_name):
                candidates.append(device)

        if not candidates:
            return None

        # Sort by load (active tasks / max tasks)
        def load_score(d: Device) -> float:
            if d.capabilities.max_concurrent_tasks == 0:
                return 1.0
            load = d.metrics.active_tasks / d.capabilities.max_concurrent_tasks
            # Prefer local device slightly
            if d.id == "local":
                load -= 0.1
            return load

        candidates.sort(key=load_score)
        return candidates[0]

    def select_by_capabilities(
        self,
        requires_docker: bool = False,
        requires_node: bool = False,
        min_memory_gb: float = 0,
        tags: list[str] | None = None,
    ) -> list[Device]:
        """
        Select devices matching capability requirements.

        Args:
            requires_docker: Must have Docker
            requires_node: Must have Node.js
            min_memory_gb: Minimum memory required
            tags: Required tags

        Returns:
            List of matching devices
        """
        matches = []

        for device in self.get_available():
            caps = device.capabilities

            if requires_docker and not caps.has_docker:
                continue
            if requires_node and not caps.has_node:
                continue
            if caps.memory_gb < min_memory_gb:
                continue
            if tags and not all(t in device.tags for t in tags):
                continue

            matches.append(device)

        return matches

    # ═══════════════════════════════════════════════════════════════
    # Health Monitoring
    # ═══════════════════════════════════════════════════════════════

    def update_heartbeat(self, device_id: str) -> bool:
        """
        Update device heartbeat.

        Args:
            device_id: ID of device

        Returns:
            True if device exists
        """
        device = self.devices.get(device_id)
        if device:
            device.update_heartbeat()
            if device.status == DeviceStatus.OFFLINE:
                device.set_online()
            return True
        return False

    def update_metrics(self, device_id: str, metrics: dict) -> bool:
        """
        Update device metrics.

        Args:
            device_id: ID of device
            metrics: Metrics dictionary

        Returns:
            True if device exists
        """
        device = self.devices.get(device_id)
        if device:
            device.metrics.cpu_usage = metrics.get("cpu_usage", 0)
            device.metrics.memory_usage = metrics.get("memory_usage", 0)
            device.metrics.disk_usage = metrics.get("disk_usage", 0)
            device.metrics.active_tasks = metrics.get("active_tasks", 0)
            device.update_heartbeat()
            return True
        return False

    async def check_stale_devices(self) -> list[str]:
        """
        Check for devices that haven't sent heartbeat.

        Returns:
            List of device IDs marked as offline
        """
        stale = []
        now = datetime.utcnow()

        for device in self.devices.values():
            if device.id == "local":
                continue

            if device.status == DeviceStatus.ONLINE:
                if device.last_seen:
                    if now - device.last_seen > self.heartbeat_timeout:
                        device.set_offline()
                        stale.append(device.id)
                        logger.warning(f"Device {device.name} marked offline (no heartbeat)")

                        if self._on_device_disconnected:
                            await self._on_device_disconnected(device)

        return stale

    async def start_heartbeat_monitor(self, interval: float = 10.0) -> None:
        """Start background heartbeat monitoring."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            return

        async def monitor_loop():
            while True:
                try:
                    await self.check_stale_devices()
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Heartbeat monitor error: {e}")
                    await asyncio.sleep(interval)

        self._heartbeat_task = asyncio.create_task(monitor_loop())

    async def stop_heartbeat_monitor(self) -> None:
        """Stop background heartbeat monitoring."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

    # ═══════════════════════════════════════════════════════════════
    # Event Callbacks
    # ═══════════════════════════════════════════════════════════════

    def on_device_connected(
        self, callback: Callable[[Device], Awaitable[None]]
    ) -> None:
        """Register callback for device connection."""
        self._on_device_connected = callback

    def on_device_disconnected(
        self, callback: Callable[[Device], Awaitable[None]]
    ) -> None:
        """Register callback for device disconnection."""
        self._on_device_disconnected = callback

    # ═══════════════════════════════════════════════════════════════
    # Task Management
    # ═══════════════════════════════════════════════════════════════

    def queue_task(self, device_id: str, task: DeviceTask) -> bool:
        """
        Queue a task for a device.

        Args:
            device_id: Target device ID
            task: Task to queue

        Returns:
            True if queued successfully
        """
        if device_id not in self.devices:
            return False

        task.device_id = device_id
        if device_id not in self.task_queue:
            self.task_queue[device_id] = []

        self.task_queue[device_id].append(task)
        return True

    def get_pending_tasks(self, device_id: str) -> list[DeviceTask]:
        """Get pending tasks for a device."""
        return self.task_queue.get(device_id, [])

    def complete_task(self, device_id: str, task_id: str, result: dict) -> bool:
        """
        Mark a task as complete.

        Args:
            device_id: Device that completed the task
            task_id: ID of completed task
            result: Task result

        Returns:
            True if task found and updated
        """
        tasks = self.task_queue.get(device_id, [])
        for task in tasks:
            if task.id == task_id:
                task.status = "completed"
                task.completed_at = datetime.utcnow()
                task.result = result.get("result")
                task.output = result.get("output")
                task.error = result.get("error")

                # Update device metrics
                device = self.devices.get(device_id)
                if device:
                    device.metrics.completed_tasks += 1
                    device.metrics.active_tasks = max(0, device.metrics.active_tasks - 1)

                return True
        return False


# ═══════════════════════════════════════════════════════════════
# Module-level singleton
# ═══════════════════════════════════════════════════════════════

_registry: DeviceRegistry | None = None


def get_device_registry() -> DeviceRegistry:
    """Get the singleton device registry instance."""
    global _registry
    if _registry is None:
        _registry = DeviceRegistry()
    return _registry


__all__ = ["DeviceRegistry", "get_device_registry"]
