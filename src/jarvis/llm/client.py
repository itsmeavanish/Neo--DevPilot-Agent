"""
LLM Client abstraction for JARVIS.

Provides a unified interface for the FreeLLM provider.
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
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        pass

    @abstractmethod
    async def list_models(self) -> list[str]:
        pass


def create_llm_client(**kwargs) -> LLMClient:
    """Create a FreeLLM client instance."""
    from jarvis.llm.providers.freellm import FreeLLMClient
    return FreeLLMClient(**kwargs)


__all__ = ["LLMClient", "ChatMessage", "LLMResponse", "create_llm_client"]
