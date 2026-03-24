"""
JARVIS API Module.

FastAPI-based REST API for the autonomous developer OS.
"""

from jarvis.api.deps import get_agent, get_tool_registry

__all__ = ["get_agent", "get_tool_registry"]
