"""
System-wide constants for JARVIS.
"""

from enum import Enum, IntEnum, auto


class RiskLevel(IntEnum):
    """Risk levels for operations."""
    LOW = 1       # Read-only, no side effects
    MEDIUM = 2    # Local modifications
    HIGH = 3      # System changes, external calls
    CRITICAL = 4  # Destructive, irreversible


class TaskStatus(str, Enum):
    """Status of a task in the system."""
    QUEUED = "queued"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Status of a step within a task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ApprovalMode(str, Enum):
    """How to handle approval for risky operations."""
    AUTO = "auto"           # Auto-approve LOW/MEDIUM risk
    CONFIRM = "confirm"     # Ask for HIGH+ risk
    STRICT = "strict"       # Ask for everything
    DRY_RUN = "dry_run"     # Never execute, just plan


class OnError(str, Enum):
    """What to do when a step fails."""
    ABORT = "abort"         # Stop execution
    RETRY = "retry"         # Retry with backoff
    CONTINUE = "continue"   # Skip and continue
    SELF_HEAL = "self_heal" # Attempt auto-fix


class MemoryType(str, Enum):
    """Types of memory items."""
    CONTEXT = "context"           # Project/file context
    ERROR = "error"               # Error occurrences
    ERROR_FIX = "error_fix"       # Successful error fixes
    PATTERN = "pattern"           # Execution patterns
    PREFERENCE = "preference"     # User preferences
    COMMAND_HISTORY = "command_history"


class DeviceType(str, Enum):
    """Types of registered devices."""
    LOCAL = "local"
    SSH = "ssh"
    GRPC = "grpc"


class EventType(str, Enum):
    """Types of system events."""
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    TOOL_EXECUTED = "tool_executed"
    MEMORY_UPDATED = "memory_updated"
    SELF_HEAL_TRIGGERED = "self_heal_triggered"


# Default timeouts (in seconds)
DEFAULT_COMMAND_TIMEOUT = 60
DEFAULT_LLM_TIMEOUT = 120
DEFAULT_TOOL_TIMEOUT = 30

# Limits
MAX_PLAN_STEPS = 20
MAX_RETRY_ATTEMPTS = 3
MAX_CONTEXT_TOKENS = 8000

# Allowlisted commands (base set)
COMMAND_ALLOWLIST = {
    # Package managers
    "npm", "npx", "yarn", "pnpm", "bun",
    "pip", "pip3", "python", "python3", "uv",
    "cargo", "rustc",
    "go",
    "dotnet",

    # Build tools
    "make", "cmake", "gradle", "mvn",

    # Version control
    "git",

    # Containers
    "docker", "docker-compose", "podman",

    # Node.js
    "node", "ts-node", "tsx",

    # System info (read-only)
    "cat", "ls", "dir", "pwd", "cd", "echo", "type", "where", "which",
    "head", "tail", "wc", "find", "grep",

    # Network (read-only)
    "ping", "curl", "wget",

    # Editors
    "code", "cursor",
}

__all__ = [
    "RiskLevel",
    "TaskStatus",
    "StepStatus",
    "ApprovalMode",
    "OnError",
    "MemoryType",
    "DeviceType",
    "EventType",
    "DEFAULT_COMMAND_TIMEOUT",
    "DEFAULT_LLM_TIMEOUT",
    "DEFAULT_TOOL_TIMEOUT",
    "MAX_PLAN_STEPS",
    "MAX_RETRY_ATTEMPTS",
    "MAX_CONTEXT_TOKENS",
    "COMMAND_ALLOWLIST",
]
