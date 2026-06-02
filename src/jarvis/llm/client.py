"""
LLM Client abstraction for JARVIS.

Provides a unified interface for different LLM providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator

from jarvis.core.logging import get_logger

logger = get_logger("jarvis.llm.client")


@dataclass
class ChatMessage:
    """A message in a chat conversation."""
    role: str  # "system", "user", "assistant"
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    """Response from an LLM."""
    content: str
    model: str
    usage: dict[str, int] | None = None
    finish_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "model": self.model,
            "usage": self.usage,
            "finish_reason": self.finish_reason,
        }


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        **kwargs,
    ) -> str:
        """
        Send a chat message and get a response.

        Args:
            messages: List of messages with 'role' and 'content'
            system: Optional system prompt
            **kwargs: Provider-specific options

        Returns:
            The assistant's response content
        """
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Send a chat message and stream the response.

        Args:
            messages: List of messages with 'role' and 'content'
            system: Optional system prompt
            **kwargs: Provider-specific options

        Yields:
            Chunks of the assistant's response
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the LLM provider is available."""
        pass

    @abstractmethod
    async def list_models(self) -> list[str]:
        """List available models."""
        pass


def create_llm_client(
    provider: str = "ollama",
    **kwargs,
) -> LLMClient:
    """
    Factory function to create an LLM client.

    Args:
        provider: Provider name ("ollama", "copilot", "openai", "anthropic")
        **kwargs: Provider-specific configuration

    Returns:
        Configured LLMClient instance
    """
    if provider == "ollama":
        from jarvis.llm.providers.ollama import OllamaClient
        return OllamaClient(**kwargs)

    elif provider == "copilot":
        from jarvis.llm.providers.copilot import CopilotClient
        return CopilotClient(**kwargs)

    elif provider == "openai":
        from jarvis.llm.providers.openai import OpenAIClient
        return OpenAIClient(**kwargs)

    elif provider == "anthropic":
        from jarvis.llm.providers.anthropic import AnthropicClient
        return AnthropicClient(**kwargs)

    elif provider == "gemini":
        from jarvis.llm.providers.gemini import GeminiClient
        return GeminiClient(**kwargs)

    elif provider == "freellm":
        from jarvis.llm.providers.freellm import FreeLLMClient
        return FreeLLMClient(**kwargs)

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


__all__ = ["LLMClient", "ChatMessage", "LLMResponse", "create_llm_client"]
