"""
Dependency injection for JARVIS API.

Provides shared dependencies for API routes.
"""

from jarvis.agent import AgentLoop
from jarvis.tools.registry import ToolRegistry, tool_registry, load_builtin_tools
from jarvis.llm import create_llm_client


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
    """Get the agent loop instance with FreeLLM client."""
    global _agent_loop
    _initialize()

    client = create_llm_client()

    if _agent_loop is None:
        _agent_loop = AgentLoop(
            tool_registry_instance=tool_registry,
            llm_client=client,
        )
    else:
        _agent_loop.set_llm_client(client)

    return _agent_loop


async def get_agent_async() -> AgentLoop:
    """Async dependency for agent loop."""
    return get_agent()


__all__ = ["get_tool_registry", "get_agent", "get_agent_async"]
