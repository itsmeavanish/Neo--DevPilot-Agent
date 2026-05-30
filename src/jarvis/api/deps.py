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
    """Get the agent loop instance with dynamic LLM client updates."""
    global _agent_loop
    _initialize()

    from jarvis.runtime_llm import get_effective_ai_provider, get_effective_ollama_host, get_effective_ollama_model
    from jarvis.config import get_settings
    from jarvis.auth.github_token_store import get_stored_github_token
    
    settings = get_settings()
    provider = get_effective_ai_provider() or "auto"
    
    if provider == "auto":
        if get_stored_github_token():
            provider = "copilot"
        elif settings.openai_api_key:
            provider = "openai"
        elif getattr(settings, "gemini_api_key", None):
            provider = "gemini"
        else:
            provider = "ollama"

    client = None
    if provider == "ollama":
        client = create_llm_client(
            provider="ollama",
            host=get_effective_ollama_host(),
            model=get_effective_ollama_model(),
        )
    elif provider == "openai":
        client = create_llm_client(
            provider="openai",
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    elif provider == "gemini":
        client = create_llm_client(
            provider="gemini",
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )
    elif provider == "copilot":
        client = create_llm_client(
            provider="copilot",
        )

    if _agent_loop is None:
        _agent_loop = AgentLoop(
            tool_registry_instance=tool_registry,
            llm_client=client,
        )
    else:
        if client:
            _agent_loop.set_llm_client(client)

    return _agent_loop


async def get_agent_async() -> AgentLoop:
    """Async dependency for agent loop."""
    return get_agent()


__all__ = ["get_tool_registry", "get_agent", "get_agent_async"]
