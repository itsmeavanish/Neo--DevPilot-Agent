"""
Device communication protocol.

WebSocket-based communication for device orchestration.
"""

import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field

from jarvis.core.logging import get_logger
from jarvis.devices.models.device import Device, DeviceTask
from jarvis.devices.registry import DeviceRegistry, get_device_registry

logger = get_logger("jarvis.devices.protocol")


class MessageType(Enum):
    """Types of messages in the device protocol."""
    # Connection management
    HELLO = "hello"
    WELCOME = "welcome"
    GOODBYE = "goodbye"

    # Health
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    METRICS = "metrics"

    # Task management
    TASK_ASSIGN = "task_assign"
    TASK_ACCEPT = "task_accept"
    TASK_REJECT = "task_reject"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    TASK_CANCEL = "task_cancel"

    # Sync
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"
    STATE_UPDATE = "state_update"

    # Error
    ERROR = "error"


@dataclass
class DeviceMessage:
    """
    Message exchanged between devices.
    """
    type: MessageType
    sender_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    message_id: str = ""
    timestamp: str = ""
    reply_to: str | None = None

    def __post_init__(self):
        if not self.message_id:
            from uuid import uuid4
            self.message_id = str(uuid4())[:12]
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        if isinstance(self.type, str):
            self.type = MessageType(self.type)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps({
            "type": self.type.value,
            "sender_id": self.sender_id,
            "payload": self.payload,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "reply_to": self.reply_to,
        })

    @classmethod
    def from_json(cls, data: str | dict) -> "DeviceMessage":
        """Deserialize from JSON."""
        if isinstance(data, str):
            data = json.loads(data)
        return cls(
            type=MessageType(data["type"]),
            sender_id=data["sender_id"],
            payload=data.get("payload", {}),
            message_id=data.get("message_id", ""),
            timestamp=data.get("timestamp", ""),
            reply_to=data.get("reply_to"),
        )

    def reply(self, payload: dict[str, Any], msg_type: MessageType | None = None) -> "DeviceMessage":
        """Create a reply message."""
        return DeviceMessage(
            type=msg_type or self.type,
            sender_id="",  # Will be set by sender
            payload=payload,
            reply_to=self.message_id,
        )


class DeviceProtocol:
    """
    Protocol handler for device communication.

    Manages message routing, serialization, and handlers.
    """

    def __init__(self, registry: DeviceRegistry | None = None):
        self.registry = registry or get_device_registry()
        self.handlers: dict[MessageType, Callable] = {}
        self.pending_responses: dict[str, asyncio.Future] = {}

        # Register default handlers
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default message handlers."""
        self.handlers[MessageType.HELLO] = self._handle_hello
        self.handlers[MessageType.HEARTBEAT] = self._handle_heartbeat
        self.handlers[MessageType.METRICS] = self._handle_metrics
        self.handlers[MessageType.TASK_COMPLETE] = self._handle_task_complete
        self.handlers[MessageType.TASK_FAILED] = self._handle_task_failed
        self.handlers[MessageType.TASK_PROGRESS] = self._handle_task_progress

    def register_handler(
        self,
        msg_type: MessageType,
        handler: Callable[[DeviceMessage], Awaitable[DeviceMessage | None]],
    ) -> None:
        """Register a custom message handler."""
        self.handlers[msg_type] = handler

    async def handle_message(
        self,
        message: DeviceMessage | str | dict,
    ) -> DeviceMessage | None:
        """
        Handle an incoming message.

        Args:
            message: Message to handle (can be raw JSON)

        Returns:
            Response message or None
        """
        if isinstance(message, (str, dict)):
            message = DeviceMessage.from_json(message)

        # Check if this is a response to a pending request
        if message.reply_to and message.reply_to in self.pending_responses:
            future = self.pending_responses.pop(message.reply_to)
            future.set_result(message)
            return None

        # Find and invoke handler
        handler = self.handlers.get(message.type)
        if handler:
            try:
                return await handler(message)
            except Exception as e:
                logger.error(f"Handler error for {message.type}: {e}")
                return DeviceMessage(
                    type=MessageType.ERROR,
                    sender_id=self.registry.local_device.id if self.registry.local_device else "unknown",
                    payload={"error": str(e), "original_type": message.type.value},
                    reply_to=message.message_id,
                )

        logger.warning(f"No handler for message type: {message.type}")
        return None

    async def send_and_wait(
        self,
        message: DeviceMessage,
        timeout: float = 30.0,
    ) -> DeviceMessage | None:
        """
        Send a message and wait for response.

        Args:
            message: Message to send
            timeout: Timeout in seconds

        Returns:
            Response message or None on timeout
        """
        future: asyncio.Future = asyncio.Future()
        self.pending_responses[message.message_id] = future

        try:
            # The actual sending is handled by the transport layer
            # This method just sets up the response tracking
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            self.pending_responses.pop(message.message_id, None)
            return None

    # ═══════════════════════════════════════════════════════════════
    # Default Handlers
    # ═══════════════════════════════════════════════════════════════

    async def _handle_hello(self, message: DeviceMessage) -> DeviceMessage:
        """Handle HELLO message (device registration)."""
        device_data = message.payload.get("device", {})
        device = Device.from_dict(device_data)
        device.id = message.sender_id

        self.registry.register(device)
        device.set_online()

        logger.info(f"Device connected: {device.name} ({device.id})")

        return DeviceMessage(
            type=MessageType.WELCOME,
            sender_id=self.registry.local_device.id if self.registry.local_device else "controller",
            payload={
                "accepted": True,
                "controller_id": self.registry.local_device.id if self.registry.local_device else "controller",
                "devices": [d.to_dict() for d in self.registry.get_online()],
            },
            reply_to=message.message_id,
        )

    async def _handle_heartbeat(self, message: DeviceMessage) -> DeviceMessage:
        """Handle HEARTBEAT message."""
        self.registry.update_heartbeat(message.sender_id)

        return DeviceMessage(
            type=MessageType.HEARTBEAT_ACK,
            sender_id=self.registry.local_device.id if self.registry.local_device else "controller",
            payload={"received_at": datetime.utcnow().isoformat()},
            reply_to=message.message_id,
        )

    async def _handle_metrics(self, message: DeviceMessage) -> DeviceMessage | None:
        """Handle METRICS message."""
        metrics = message.payload.get("metrics", {})
        self.registry.update_metrics(message.sender_id, metrics)
        return None  # No response needed

    async def _handle_task_complete(self, message: DeviceMessage) -> None:
        """Handle TASK_COMPLETE message."""
        task_id = message.payload.get("task_id")
        result = message.payload.get("result", {})

        if task_id:
            self.registry.complete_task(message.sender_id, task_id, result)
            logger.info(f"Task {task_id} completed by {message.sender_id}")

        return None

    async def _handle_task_failed(self, message: DeviceMessage) -> None:
        """Handle TASK_FAILED message."""
        task_id = message.payload.get("task_id")
        error = message.payload.get("error", "Unknown error")

        if task_id:
            self.registry.complete_task(
                message.sender_id,
                task_id,
                {"error": error, "status": "failed"},
            )
            logger.warning(f"Task {task_id} failed on {message.sender_id}: {error}")

        return None

    async def _handle_task_progress(self, message: DeviceMessage) -> None:
        """Handle TASK_PROGRESS message."""
        task_id = message.payload.get("task_id")
        progress = message.payload.get("progress", 0)
        status = message.payload.get("status", "")

        logger.debug(f"Task {task_id} progress: {progress}% - {status}")
        return None

    # ═══════════════════════════════════════════════════════════════
    # Message Builders
    # ═══════════════════════════════════════════════════════════════

    def create_hello(self, device: Device) -> DeviceMessage:
        """Create a HELLO message for device registration."""
        return DeviceMessage(
            type=MessageType.HELLO,
            sender_id=device.id,
            payload={"device": device.to_dict()},
        )

    def create_heartbeat(self, device: Device) -> DeviceMessage:
        """Create a HEARTBEAT message."""
        return DeviceMessage(
            type=MessageType.HEARTBEAT,
            sender_id=device.id,
            payload={"timestamp": datetime.utcnow().isoformat()},
        )

    def create_metrics(self, device: Device) -> DeviceMessage:
        """Create a METRICS message."""
        return DeviceMessage(
            type=MessageType.METRICS,
            sender_id=device.id,
            payload={"metrics": device.metrics.to_dict()},
        )

    def create_task_assign(self, task: DeviceTask) -> DeviceMessage:
        """Create a TASK_ASSIGN message."""
        return DeviceMessage(
            type=MessageType.TASK_ASSIGN,
            sender_id=self.registry.local_device.id if self.registry.local_device else "controller",
            payload={"task": task.to_dict()},
        )

    def create_task_complete(
        self,
        task_id: str,
        result: Any,
        output: str | None = None,
    ) -> DeviceMessage:
        """Create a TASK_COMPLETE message."""
        return DeviceMessage(
            type=MessageType.TASK_COMPLETE,
            sender_id=self.registry.local_device.id if self.registry.local_device else "worker",
            payload={
                "task_id": task_id,
                "result": {"result": result, "output": output},
            },
        )

    def create_task_failed(
        self,
        task_id: str,
        error: str,
    ) -> DeviceMessage:
        """Create a TASK_FAILED message."""
        return DeviceMessage(
            type=MessageType.TASK_FAILED,
            sender_id=self.registry.local_device.id if self.registry.local_device else "worker",
            payload={
                "task_id": task_id,
                "error": error,
            },
        )


__all__ = ["MessageType", "DeviceMessage", "DeviceProtocol"]
