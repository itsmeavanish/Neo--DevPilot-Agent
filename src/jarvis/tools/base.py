"""
Base tool abstraction for JARVIS.

All tools must inherit from BaseTool and implement the execute method.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

from jarvis.core.constants import RiskLevel
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.tools.base")


@dataclass
class ToolResult:
    """
    Result of a tool execution.

    Attributes:
        status: "success" or "error"
        output: The output data from the tool
        error: Error message if status is "error"
        metadata: Additional metadata about the execution
    """
    status: str  # "success" | "error"
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.metadata["timestamp"] = datetime.utcnow().isoformat() + "Z"

    @property
    def is_success(self) -> bool:
        return self.status == "success"

    @property
    def is_error(self) -> bool:
        return self.status == "error"

    @classmethod
    def success(cls, output: Any, **metadata) -> "ToolResult":
        """Create a successful result."""
        return cls(status="success", output=output, metadata=metadata)

    @classmethod
    def failure(cls, error: str, **metadata) -> "ToolResult":
        """Create a failed result."""
        return cls(status="error", error=error, metadata=metadata)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseTool(ABC):
    """
    Abstract base class for all JARVIS tools.

    Every tool must define:
    - name: Unique identifier for the tool
    - description: Human-readable description
    - schema: JSON Schema for parameters
    - execute(): Async method to run the tool

    Optional:
    - risk_level: Risk level (default: MEDIUM)
    - requires_approval: Whether to always ask for approval
    - timeout: Default timeout in seconds
    """

    # Class-level attributes (must be overridden)
    name: ClassVar[str]
    description: ClassVar[str]
    schema: ClassVar[dict]

    # Optional class-level attributes
    risk_level: ClassVar[RiskLevel] = RiskLevel.MEDIUM
    requires_approval: ClassVar[bool] = False
    timeout: ClassVar[int] = 30

    def __init__(self):
        self.logger = get_logger(f"jarvis.tools.{self.name}")

    @abstractmethod
    async def execute(self, params: dict) -> ToolResult:
        """
        Execute the tool with the given parameters.

        Args:
            params: Dictionary of parameters matching the tool's schema

        Returns:
            ToolResult with the outcome of the execution
        """
        pass

    def validate_params(self, params: dict) -> list[str]:
        """
        Validate parameters against the tool's schema.

        Args:
            params: Parameters to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        from jarvis.tools.schema import validate_params
        return validate_params(params, self.schema)

    def get_schema_for_llm(self) -> dict:
        """
        Get the tool schema in OpenAI function calling format.

        Returns:
            Dictionary suitable for LLM function calling
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema,
            }
        }

    def __repr__(self) -> str:
        return f"<Tool:{self.name} risk={self.risk_level.name}>"


class ToolContext:
    """
    Context passed to tools during execution.

    Contains information about the current execution environment.
    """

    def __init__(
        self,
        working_dir: str | None = None,
        env_vars: dict[str, str] | None = None,
        task_id: str | None = None,
        session_id: str | None = None,
    ):
        self.working_dir = working_dir
        self.env_vars = env_vars or {}
        self.task_id = task_id
        self.session_id = session_id

    def to_dict(self) -> dict:
        return {
            "working_dir": self.working_dir,
            "task_id": self.task_id,
            "session_id": self.session_id,
        }


__all__ = ["BaseTool", "ToolResult", "ToolContext"]
