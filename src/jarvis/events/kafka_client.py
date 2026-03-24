"""
Kafka Event Bus for JARVIS.

Provides pub/sub messaging using Apache Kafka for:
- Agent task coordination
- Real-time notifications
- Workflow events
- System monitoring
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field, asdict
from enum import Enum

from jarvis.core.logging import get_logger

logger = get_logger("jarvis.events.kafka")


class EventType(str, Enum):
    """Event types in JARVIS system."""
    # Agent events
    AGENT_TASK_STARTED = "agent.task.started"
    AGENT_TASK_COMPLETED = "agent.task.completed"
    AGENT_TASK_FAILED = "agent.task.failed"
    AGENT_STEP_EXECUTED = "agent.step.executed"

    # Workflow events
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_STEP = "workflow.step"

    # Tool events
    TOOL_EXECUTED = "tool.executed"
    TOOL_FAILED = "tool.failed"

    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"
    SYSTEM_HEALTH = "system.health"

    # User events
    USER_COMMAND = "user.command"
    USER_FEEDBACK = "user.feedback"

    # Memory events
    MEMORY_STORED = "memory.stored"
    MEMORY_RETRIEVED = "memory.retrieved"

    # Device events
    DEVICE_CONNECTED = "device.connected"
    DEVICE_DISCONNECTED = "device.disconnected"
    DEVICE_COMMAND = "device.command"


@dataclass
class Event:
    """
    Event message for Kafka pub/sub.

    Attributes:
        type: Event type from EventType enum
        data: Event payload
        source: Service/component that generated the event
        id: Unique event identifier
        timestamp: Event creation time
        correlation_id: For tracking related events
    """
    type: EventType | str
    data: dict[str, Any] = field(default_factory=dict)
    source: str = "jarvis"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    correlation_id: str | None = None

    def to_json(self) -> str:
        """Serialize event to JSON."""
        d = asdict(self)
        if isinstance(d["type"], EventType):
            d["type"] = d["type"].value
        return json.dumps(d)

    @classmethod
    def from_json(cls, data: str) -> "Event":
        """Deserialize event from JSON."""
        d = json.loads(data)
        # Try to convert type to EventType enum
        try:
            d["type"] = EventType(d["type"])
        except ValueError:
            pass  # Keep as string if not in enum
        return cls(**d)


# Type alias for event handlers
EventHandler = Callable[[Event], Awaitable[None]]


class KafkaEventBus:
    """
    Kafka-based event bus for JARVIS.

    Provides async pub/sub messaging with:
    - Automatic topic creation
    - Consumer groups for load balancing
    - Event serialization/deserialization
    - In-memory fallback when Kafka unavailable
    """

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        client_id: str = "jarvis",
        group_id: str = "jarvis-group",
        enable_fallback: bool = True,
    ):
        """
        Initialize Kafka event bus.

        Args:
            bootstrap_servers: Kafka broker addresses
            client_id: Client identifier
            group_id: Consumer group ID
            enable_fallback: Use in-memory fallback if Kafka unavailable
        """
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self.group_id = group_id
        self.enable_fallback = enable_fallback

        self._producer = None
        self._consumer = None
        self._handlers: dict[str, list[EventHandler]] = {}
        self._running = False
        self._use_fallback = False
        self._fallback_queue: asyncio.Queue[Event] = asyncio.Queue()

        self.logger = get_logger("jarvis.events.kafka")

    async def connect(self) -> bool:
        """
        Connect to Kafka cluster.

        Returns:
            True if connected, False if using fallback
        """
        try:
            from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

            # Create producer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=f"{self.client_id}-producer",
                value_serializer=lambda v: v.encode("utf-8"),
            )
            await self._producer.start()

            self.logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
            self._use_fallback = False
            return True

        except ImportError:
            self.logger.warning("aiokafka not installed. Using in-memory fallback.")
            self._use_fallback = True
            return False
        except Exception as e:
            self.logger.warning(f"Failed to connect to Kafka: {e}. Using in-memory fallback.")
            self._use_fallback = True
            return False

    async def disconnect(self):
        """Disconnect from Kafka."""
        self._running = False

        if self._producer:
            await self._producer.stop()
            self._producer = None

        if self._consumer:
            await self._consumer.stop()
            self._consumer = None

        self.logger.info("Disconnected from Kafka")

    async def publish(self, topic: str, event: Event) -> bool:
        """
        Publish an event to a topic.

        Args:
            topic: Kafka topic name
            event: Event to publish

        Returns:
            True if published successfully
        """
        try:
            if self._use_fallback:
                # In-memory fallback
                await self._fallback_queue.put(event)

                # Trigger handlers for this topic
                if topic in self._handlers:
                    for handler in self._handlers[topic]:
                        try:
                            await handler(event)
                        except Exception as e:
                            self.logger.error(f"Handler error: {e}")

                return True

            if not self._producer:
                await self.connect()

            if self._producer:
                await self._producer.send_and_wait(
                    topic,
                    event.to_json(),
                )
                self.logger.debug(f"Published {event.type} to {topic}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to publish event: {e}")
            return False

    async def subscribe(
        self,
        topics: list[str],
        handler: EventHandler,
    ):
        """
        Subscribe to topics with a handler.

        Args:
            topics: List of topic names to subscribe
            handler: Async function to handle events
        """
        for topic in topics:
            if topic not in self._handlers:
                self._handlers[topic] = []
            self._handlers[topic].append(handler)

        self.logger.info(f"Subscribed to topics: {topics}")

    async def start_consuming(self):
        """Start consuming messages from subscribed topics."""
        if not self._handlers:
            self.logger.warning("No handlers registered, skipping consumer start")
            return

        self._running = True

        if self._use_fallback:
            # In-memory fallback consumer
            asyncio.create_task(self._fallback_consumer_loop())
            return

        try:
            from aiokafka import AIOKafkaConsumer

            topics = list(self._handlers.keys())

            self._consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                client_id=f"{self.client_id}-consumer",
                value_deserializer=lambda v: v.decode("utf-8"),
            )
            await self._consumer.start()

            asyncio.create_task(self._consumer_loop())
            self.logger.info(f"Started consuming from {topics}")

        except Exception as e:
            self.logger.error(f"Failed to start consumer: {e}")

    async def _consumer_loop(self):
        """Main consumer loop for Kafka messages."""
        try:
            async for msg in self._consumer:
                if not self._running:
                    break

                try:
                    event = Event.from_json(msg.value)
                    topic = msg.topic

                    if topic in self._handlers:
                        for handler in self._handlers[topic]:
                            try:
                                await handler(event)
                            except Exception as e:
                                self.logger.error(f"Handler error for {event.type}: {e}")

                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse event: {e}")
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")

        except Exception as e:
            self.logger.error(f"Consumer loop error: {e}")

    async def _fallback_consumer_loop(self):
        """In-memory fallback consumer loop."""
        self.logger.info("Started in-memory fallback consumer")

        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._fallback_queue.get(),
                    timeout=1.0
                )
                # Events are handled in publish() for fallback mode

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Fallback consumer error: {e}")

    async def emit(
        self,
        event_type: EventType | str,
        data: dict[str, Any] | None = None,
        topic: str | None = None,
        correlation_id: str | None = None,
    ) -> bool:
        """
        Convenience method to emit an event.

        Args:
            event_type: Type of event
            data: Event data payload
            topic: Topic to publish to (defaults to event type category)
            correlation_id: For tracking related events

        Returns:
            True if emitted successfully
        """
        event = Event(
            type=event_type,
            data=data or {},
            correlation_id=correlation_id,
        )

        # Default topic based on event type
        if topic is None:
            if isinstance(event_type, EventType):
                topic = event_type.value.split(".")[0]  # e.g., "agent" from "agent.task.started"
            else:
                topic = str(event_type).split(".")[0]

        return await self.publish(topic, event)

    @property
    def is_connected(self) -> bool:
        """Check if connected to Kafka."""
        return self._producer is not None and not self._use_fallback

    @property
    def is_using_fallback(self) -> bool:
        """Check if using in-memory fallback."""
        return self._use_fallback


# Global event bus instance
_event_bus: KafkaEventBus | None = None


def get_event_bus() -> KafkaEventBus:
    """Get or create global event bus instance."""
    global _event_bus
    if _event_bus is None:
        from jarvis.config import get_settings
        settings = get_settings()

        _event_bus = KafkaEventBus(
            bootstrap_servers=getattr(settings, "kafka_bootstrap_servers", "localhost:9092"),
            client_id="jarvis",
            group_id="jarvis-main",
        )
    return _event_bus


async def init_event_bus() -> KafkaEventBus:
    """Initialize and connect the global event bus."""
    bus = get_event_bus()
    await bus.connect()
    return bus


__all__ = [
    "Event",
    "EventType",
    "EventHandler",
    "KafkaEventBus",
    "get_event_bus",
    "init_event_bus",
]
