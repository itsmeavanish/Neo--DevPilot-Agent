"""
Dependency injection for JARVIS API.

Provides shared dependencies for API routes.
"""

from functools import lru_cache
from typing import AsyncGenerator

from jarvis.agent import AgentLoop
from jarvis.tools.registry import ToolRegistry, tool_registry, load_builtin_tools
from jarvis.llm import create_llm_client
from jarvis.config import get_settings


# Global instances
_agent_loop: AgentLoop | None = None
_initialized = False


def _initialize():
    """Initialize the system (tools, LLM, etc.)."""
    global _initialized
    if _initialized:
        return

    # Load built-in tools
    load_builtin_tools()
    _initialized = True


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    _initialize()
    return tool_registry


def get_agent() -> AgentLoop:
    """Get the agent loop instance."""
    global _agent_loop
    _initialize()

    if _agent_loop is None:
        settings = get_settings()

        # Create LLM client if configured
        llm_client = None
        if settings.ollama_host:
            llm_client = create_llm_client(
                provider="ollama",
                host=settings.ollama_host,
                model=settings.ollama_model,
            )

        _agent_loop = AgentLoop(
            tool_registry_instance=tool_registry,
            llm_client=llm_client,
        )

    return _agent_loop


async def get_agent_async() -> AgentLoop:
    """Async dependency for agent loop."""
    return get_agent()


__all__ = ["get_tool_registry", "get_agent", "get_agent_async"]
