"""
Task distributor for multi-device orchestration.

Handles task routing, load balancing, and execution management.
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field

from jarvis.core.logging import get_logger
from jarvis.devices.models.device import Device, DeviceTask
from jarvis.devices.registry import DeviceRegistry, get_device_registry
from jarvis.devices.protocol import DeviceProtocol, DeviceMessage, MessageType

logger = get_logger("jarvis.devices.distributor")


class LoadBalanceStrategy(Enum):
    """Load balancing strategies for task distribution."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    CAPABILITY_MATCH = "capability_match"
    LOCAL_PREFERRED = "local_preferred"
    RANDOM = "random"


@dataclass
class DistributionResult:
    """Result of task distribution."""
    success: bool
    task_id: str
    device_id: str | None = None
    device_name: str | None = None
    error: str | None = None
    queued: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "task_id": self.task_id,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "error": self.error,
            "queued": self.queued,
        }


class TaskDistributor:
    """
    Distributes tasks across available devices.

    Features:
    - Multiple load balancing strategies
    - Task queuing when devices are busy
    - Automatic retry on failure
    - Result aggregation for parallel tasks
    """

    def __init__(
        self,
        registry: DeviceRegistry | None = None,
        protocol: DeviceProtocol | None = None,
    ):
        self.registry = registry or get_device_registry()
        self.protocol = protocol or DeviceProtocol(self.registry)

        # Configuration
        self.strategy = LoadBalanceStrategy.LOCAL_PREFERRED
        self.max_retries = 3
        self.retry_delay = 1.0
        self.task_timeout = 300.0

        # State
        self.active_tasks: dict[str, DeviceTask] = {}
        self.task_results: dict[str, Any] = {}
        self.round_robin_index = 0

        # Callbacks
        self._on_task_complete: Callable[[DeviceTask, Any], Awaitable[None]] | None = None
        self._on_task_failed: Callable[[DeviceTask, str], Awaitable[None]] | None = None

        # Send function (to be set by transport layer)
        self._send_to_device: Callable[[str, DeviceMessage], Awaitable[bool]] | None = None

    def set_send_function(
        self,
        send_fn: Callable[[str, DeviceMessage], Awaitable[bool]],
    ) -> None:
        """Set the function used to send messages to devices."""
        self._send_to_device = send_fn

    def set_strategy(self, strategy: LoadBalanceStrategy | str) -> None:
        """Set the load balancing strategy."""
        if isinstance(strategy, str):
            strategy = LoadBalanceStrategy(strategy)
        self.strategy = strategy

    # ═══════════════════════════════════════════════════════════════
    # Task Distribution
    # ═══════════════════════════════════════════════════════════════

    async def distribute(
        self,
        tool_name: str,
        params: dict[str, Any],
        priority: int = 5,
        target_device: str | None = None,
        timeout: float | None = None,
    ) -> DistributionResult:
        """
        Distribute a task to the best available device.

        Args:
            tool_name: Name of tool to execute
            params: Tool parameters
            priority: Task priority (1-10, lower is higher)
            target_device: Specific device ID to target
            timeout: Task timeout in seconds

        Returns:
            DistributionResult with assignment info
        """
        task = DeviceTask(
            tool_name=tool_name,
            params=params,
            priority=priority,
            timeout_seconds=int(timeout or self.task_timeout),
        )

        # Select target device
        if target_device:
            device = self.registry.get(target_device)
            if not device:
                return DistributionResult(
                    success=False,
                    task_id=task.id,
                    error=f"Device not found: {target_device}",
                )
            if not device.is_available:
                # Queue the task
                self.registry.queue_task(target_device, task)
                return DistributionResult(
                    success=True,
                    task_id=task.id,
                    device_id=target_device,
                    device_name=device.name,
                    queued=True,
                )
        else:
            device = self._select_device(tool_name)
            if not device:
                return DistributionResult(
                    success=False,
                    task_id=task.id,
                    error="No available device for this task",
                )

        # Assign task to device
        task.device_id = device.id
        task.status = "assigned"
        self.active_tasks[task.id] = task

        # Send task to device
        if device.id == "local":
            # Execute locally
            return await self._execute_local(task)
        else:
            # Send to remote device
            return await self._send_to_remote(device, task)

    async def distribute_parallel(
        self,
        tasks: list[tuple[str, dict[str, Any]]],
        wait_all: bool = True,
    ) -> list[DistributionResult]:
        """
        Distribute multiple tasks in parallel.

        Args:
            tasks: List of (tool_name, params) tuples
            wait_all: Wait for all tasks to complete

        Returns:
            List of distribution results
        """
        coroutines = [
            self.distribute(tool_name, params)
            for tool_name, params in tasks
        ]

        if wait_all:
            return await asyncio.gather(*coroutines)
        else:
            # Return immediately, results will come via callbacks
            asyncio.gather(*coroutines)
            return []

    def _select_device(self, tool_name: str) -> Device | None:
        """Select best device based on strategy."""
        available = self.registry.get_available()

        if not available:
            return None

        # Filter by capability
        capable = [d for d in available if d.can_execute(tool_name)]
        if not capable:
            # Fall back to any available if no specific capability match
            capable = available

        if not capable:
            return None

        if self.strategy == LoadBalanceStrategy.ROUND_ROBIN:
            return self._select_round_robin(capable)
        elif self.strategy == LoadBalanceStrategy.LEAST_LOADED:
            return self._select_least_loaded(capable)
        elif self.strategy == LoadBalanceStrategy.LOCAL_PREFERRED:
            return self._select_local_preferred(capable)
        elif self.strategy == LoadBalanceStrategy.RANDOM:
            return self._select_random(capable)
        else:
            return capable[0]

    def _select_round_robin(self, devices: list[Device]) -> Device:
        """Select device using round-robin."""
        device = devices[self.round_robin_index % len(devices)]
        self.round_robin_index += 1
        return device

    def _select_least_loaded(self, devices: list[Device]) -> Device:
        """Select device with lowest load."""
        def load_score(d: Device) -> float:
            if d.capabilities.max_concurrent_tasks == 0:
                return 1.0
            return d.metrics.active_tasks / d.capabilities.max_concurrent_tasks

        return min(devices, key=load_score)

    def _select_local_preferred(self, devices: list[Device]) -> Device:
        """Prefer local device, fall back to least loaded."""
        for d in devices:
            if d.id == "local" and d.is_available:
                return d
        return self._select_least_loaded(devices)

    def _select_random(self, devices: list[Device]) -> Device:
        """Select random device."""
        import random
        return random.choice(devices)

    # ═══════════════════════════════════════════════════════════════
    # Task Execution
    # ═══════════════════════════════════════════════════════════════

    async def _execute_local(self, task: DeviceTask) -> DistributionResult:
        """Execute task on local device."""
        from jarvis.tools.registry import tool_registry

        task.status = "running"
        task.started_at = datetime.utcnow()

        # Update device metrics
        local_device = self.registry.local_device
        if local_device:
            local_device.metrics.active_tasks += 1

        try:
            tool = tool_registry.get(task.tool_name)
            if not tool:
                raise ValueError(f"Tool not found: {task.tool_name}")

            result = await tool.execute(**task.params)

            task.status = "completed"
            task.completed_at = datetime.utcnow()
            task.result = result.data if hasattr(result, 'data') else result
            task.output = result.output if hasattr(result, 'output') else str(result)

            if local_device:
                local_device.metrics.completed_tasks += 1
                local_device.metrics.active_tasks = max(0, local_device.metrics.active_tasks - 1)

            # Callback
            if self._on_task_complete:
                await self._on_task_complete(task, task.result)

            return DistributionResult(
                success=True,
                task_id=task.id,
                device_id="local",
                device_name="local",
            )

        except Exception as e:
            task.status = "failed"
            task.completed_at = datetime.utcnow()
            task.error = str(e)

            if local_device:
                local_device.metrics.failed_tasks += 1
                local_device.metrics.active_tasks = max(0, local_device.metrics.active_tasks - 1)

            if self._on_task_failed:
                await self._on_task_failed(task, str(e))

            return DistributionResult(
                success=False,
                task_id=task.id,
                device_id="local",
                device_name="local",
                error=str(e),
            )

    async def _send_to_remote(
        self,
        device: Device,
        task: DeviceTask,
    ) -> DistributionResult:
        """Send task to remote device for execution."""
        if not self._send_to_device:
            # No transport configured, queue the task
            self.registry.queue_task(device.id, task)
            return DistributionResult(
                success=True,
                task_id=task.id,
                device_id=device.id,
                device_name=device.name,
                queued=True,
            )

        message = self.protocol.create_task_assign(task)

        try:
            sent = await self._send_to_device(device.id, message)
            if sent:
                task.status = "sent"
                device.metrics.active_tasks += 1

                return DistributionResult(
                    success=True,
                    task_id=task.id,
                    device_id=device.id,
                    device_name=device.name,
                )
            else:
                return DistributionResult(
                    success=False,
                    task_id=task.id,
                    device_id=device.id,
                    device_name=device.name,
                    error="Failed to send task to device",
                )

        except Exception as e:
            return DistributionResult(
                success=False,
                task_id=task.id,
                device_id=device.id,
                device_name=device.name,
                error=str(e),
            )

    # ═══════════════════════════════════════════════════════════════
    # Task Status
    # ═══════════════════════════════════════════════════════════════

    def get_task(self, task_id: str) -> DeviceTask | None:
        """Get task by ID."""
        return self.active_tasks.get(task_id)

    def get_active_tasks(self) -> list[DeviceTask]:
        """Get all active tasks."""
        return list(self.active_tasks.values())

    def get_task_result(self, task_id: str) -> Any:
        """Get result for a completed task."""
        task = self.active_tasks.get(task_id)
        if task and task.status == "completed":
            return task.result
        return None

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        task = self.active_tasks.get(task_id)
        if not task:
            return False

        if task.status in ("completed", "failed", "cancelled"):
            return False

        task.status = "cancelled"
        task.completed_at = datetime.utcnow()

        # Send cancel message to device if remote
        if task.device_id and task.device_id != "local" and self._send_to_device:
            message = DeviceMessage(
                type=MessageType.TASK_CANCEL,
                sender_id=self.registry.local_device.id if self.registry.local_device else "controller",
                payload={"task_id": task_id},
            )
            await self._send_to_device(task.device_id, message)

        return True

    # ═══════════════════════════════════════════════════════════════
    # Callbacks
    # ═══════════════════════════════════════════════════════════════

    def on_task_complete(
        self,
        callback: Callable[[DeviceTask, Any], Awaitable[None]],
    ) -> None:
        """Register callback for task completion."""
        self._on_task_complete = callback

    def on_task_failed(
        self,
        callback: Callable[[DeviceTask, str], Awaitable[None]],
    ) -> None:
        """Register callback for task failure."""
        self._on_task_failed = callback


# ═══════════════════════════════════════════════════════════════
# Module-level singleton
# ═══════════════════════════════════════════════════════════════

_distributor: TaskDistributor | None = None


def get_task_distributor() -> TaskDistributor:
    """Get the singleton task distributor instance."""
    global _distributor
    if _distributor is None:
        _distributor = TaskDistributor()
    return _distributor


__all__ = [
    "LoadBalanceStrategy",
    "DistributionResult",
    "TaskDistributor",
    "get_task_distributor",
]
