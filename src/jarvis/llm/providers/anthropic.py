"""
Anthropic API client for JARVIS.

Implements the LLMClient interface using the Anthropic REST API.
"""

import json
from typing import AsyncIterator

import httpx

from jarvis.llm.client import LLMClient
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.llm.anthropic")


class AnthropicClient(LLMClient):
    """Client for Anthropic API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-haiku-20240307",
        base_url: str = "https://api.anthropic.com",
    ):
        """
        Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key
            model: Model name to use
            base_url: Optional base URL override
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _convert_messages(self, messages: list[dict[str, str]]) -> list[dict]:
        """Convert standard messages to Anthropic format."""
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                # Anthropic handles system prompt separately
                continue
            anthropic_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        return anthropic_messages

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        **kwargs,
    ) -> str:
        """Send a chat message and get a response."""
        if not self.api_key:
            raise ValueError("Anthropic API key is not set")

        anthropic_messages = self._convert_messages(messages)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        if system:
            payload["system"] = system

        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=kwargs.get("timeout", 120.0),
                )
                response.raise_for_status()
                data = response.json()

                if "content" in data and len(data["content"]) > 0:
                    return data["content"][0]["text"]
                return ""

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Send a chat message and stream the response."""
        if not self.api_key:
            raise ValueError("Anthropic API key is not set")

        anthropic_messages = self._convert_messages(messages)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "accept": "text/event-stream",
        }

        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": True,
        }

        if system:
            payload["system"] = system

        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=kwargs.get("timeout", 120.0),
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue

                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            if data.get("type") == "content_block_delta" and "delta" in data:
                                yield data["delta"].get("text", "")
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Anthropic streaming error: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if the Anthropic provider is available."""
        return bool(self.api_key)

    async def list_models(self) -> list[str]:
        """List available models."""
        return [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-3-5-sonnet-20240620",
        ]
