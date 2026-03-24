"""
JARVIS Kafka Topics.

Predefined topics for the JARVIS event system.
"""

from enum import Enum


class JarvisTopics(str, Enum):
    """
    Predefined Kafka topics for JARVIS.

    Topics are organized by domain:
    - agent: AI agent task execution
    - workflow: Workflow orchestration
    - tool: Tool execution
    - system: System events and health
    - user: User interactions
    - memory: Memory operations
    - device: IoT device events
    """

    # Agent topics
    AGENT = "jarvis.agent"
    AGENT_TASKS = "jarvis.agent.tasks"
    AGENT_RESULTS = "jarvis.agent.results"

    # Workflow topics
    WORKFLOW = "jarvis.workflow"
    WORKFLOW_EVENTS = "jarvis.workflow.events"

    # Tool topics
    TOOLS = "jarvis.tools"
    TOOL_RESULTS = "jarvis.tools.results"

    # System topics
    SYSTEM = "jarvis.system"
    SYSTEM_HEALTH = "jarvis.system.health"
    SYSTEM_ERRORS = "jarvis.system.errors"
    SYSTEM_METRICS = "jarvis.system.metrics"

    # User topics
    USER = "jarvis.user"
    USER_COMMANDS = "jarvis.user.commands"
    USER_NOTIFICATIONS = "jarvis.user.notifications"

    # Memory topics
    MEMORY = "jarvis.memory"
    MEMORY_EVENTS = "jarvis.memory.events"

    # Device/IoT topics
    DEVICES = "jarvis.devices"
    DEVICE_COMMANDS = "jarvis.devices.commands"
    DEVICE_STATUS = "jarvis.devices.status"

    # IDE topics
    IDE = "jarvis.ide"
    IDE_EVENTS = "jarvis.ide.events"

    # Self-healing topics
    SELF_HEAL = "jarvis.selfheal"
    SELF_HEAL_EVENTS = "jarvis.selfheal.events"


# Topic configurations
TOPIC_CONFIGS = {
    JarvisTopics.AGENT: {
        "retention_ms": 86400000,  # 1 day
        "partitions": 3,
    },
    JarvisTopics.SYSTEM_HEALTH: {
        "retention_ms": 3600000,  # 1 hour
        "partitions": 1,
    },
    JarvisTopics.SYSTEM_ERRORS: {
        "retention_ms": 604800000,  # 7 days
        "partitions": 1,
    },
    JarvisTopics.USER_NOTIFICATIONS: {
        "retention_ms": 86400000,  # 1 day
        "partitions": 1,
    },
}


__all__ = ["JarvisTopics", "TOPIC_CONFIGS"]
