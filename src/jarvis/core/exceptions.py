"""
Custom exceptions for JARVIS.

All exceptions inherit from JarvisError for easy catching.
"""

from typing import Any


class JarvisError(Exception):
    """Base exception for all JARVIS errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


# ═══════════════════════════════════════════════════════════════
# Agent Errors
# ═══════════════════════════════════════════════════════════════

class AgentError(JarvisError):
    """Base class for agent-related errors."""
    pass


class PlanningError(AgentError):
    """Error during plan generation."""
    pass


class ExecutionError(AgentError):
    """Error during plan execution."""
    pass


class IntentParsingError(AgentError):
    """Error parsing user intent."""
    pass


# ═══════════════════════════════════════════════════════════════
# Tool Errors
# ═══════════════════════════════════════════════════════════════

class ToolError(JarvisError):
    """Base class for tool-related errors."""
    pass


class ToolNotFoundError(ToolError):
    """Requested tool does not exist."""

    def __init__(self, tool_name: str):
        super().__init__(f"Tool not found: {tool_name}")
        self.tool_name = tool_name


class ToolExecutionError(ToolError):
    """Error during tool execution."""

    def __init__(self, tool_name: str, message: str, details: dict | None = None):
        super().__init__(f"Tool '{tool_name}' failed: {message}", details)
        self.tool_name = tool_name


class ToolValidationError(ToolError):
    """Tool parameter validation failed."""

    def __init__(self, tool_name: str, errors: list[str]):
        super().__init__(f"Invalid parameters for '{tool_name}': {', '.join(errors)}")
        self.tool_name = tool_name
        self.errors = errors


class ToolTimeoutError(ToolError):
    """Tool execution timed out."""

    def __init__(self, tool_name: str, timeout: int):
        super().__init__(f"Tool '{tool_name}' timed out after {timeout}s")
        self.tool_name = tool_name
        self.timeout = timeout


# ═══════════════════════════════════════════════════════════════
# Security Errors
# ═══════════════════════════════════════════════════════════════

class SecurityError(JarvisError):
    """Base class for security-related errors."""
    pass


class AuthenticationError(SecurityError):
    """Authentication failed."""
    pass


class AuthorizationError(SecurityError):
    """User lacks required permissions."""

    def __init__(self, action: str, resource: str | None = None):
        msg = f"Not authorized to perform: {action}"
        if resource:
            msg += f" on {resource}"
        super().__init__(msg)
        self.action = action
        self.resource = resource


class CommandNotAllowedError(SecurityError):
    """Command is not in the allowlist."""

    def __init__(self, command: str):
        super().__init__(f"Command not allowed: {command.split()[0]}")
        self.command = command


class ApprovalRequiredError(SecurityError):
    """Operation requires user approval."""

    def __init__(self, operation: str, risk_level: str):
        super().__init__(f"Approval required for {risk_level} risk operation: {operation}")
        self.operation = operation
        self.risk_level = risk_level


# ═══════════════════════════════════════════════════════════════
# Memory Errors
# ═══════════════════════════════════════════════════════════════

class MemoryError(JarvisError):
    """Base class for memory-related errors."""
    pass


class EmbeddingError(MemoryError):
    """Error generating embeddings."""
    pass


# ═══════════════════════════════════════════════════════════════
# LLM Errors
# ═══════════════════════════════════════════════════════════════

class LLMError(JarvisError):
    """Base class for LLM-related errors."""
    pass


class LLMConnectionError(LLMError):
    """Cannot connect to LLM provider."""
    pass


class LLMResponseError(LLMError):
    """Invalid or unexpected LLM response."""
    pass


# Export all exceptions
__all__ = [
    "JarvisError",
    "AgentError",
    "PlanningError",
    "ExecutionError",
    "IntentParsingError",
    "ToolError",
    "ToolNotFoundError",
    "ToolExecutionError",
    "ToolValidationError",
    "ToolTimeoutError",
    "SecurityError",
    "AuthenticationError",
    "AuthorizationError",
    "CommandNotAllowedError",
    "ApprovalRequiredError",
    "MemoryError",
    "EmbeddingError",
    "LLMError",
    "LLMConnectionError",
    "LLMResponseError",
]
