"""
Tool system for JARVIS.

Provides pluggable, schema-validated tools for the agent to use.
"""

from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import ToolRegistry, tool_registry
from jarvis.tools.schema import validate_params

__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolRegistry",
    "tool_registry",
    "validate_params",
]
