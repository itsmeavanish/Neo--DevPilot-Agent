"""
JARVIS Event System.

Provides event-driven architecture using Apache Kafka for
real-time messaging and event streaming.
"""

from jarvis.events.kafka_client import KafkaEventBus, Event
from jarvis.events.topics import JarvisTopics

__all__ = ["KafkaEventBus", "Event", "JarvisTopics"]
