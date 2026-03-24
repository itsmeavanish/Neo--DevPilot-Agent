"""
OpenAI Provider.

Uses OpenAI API (GPT-4, GPT-3.5) for AI assistance.
Works in cloud deployments without local dependencies.
"""

import os
from typing import AsyncIterator

import httpx

from jarvis.llm.client import LLMClient
from jarvis.core.logging import get_logger
from jarvis.core.exceptions import LLMConnectionError, LLMResponseError

logger = get_logger("jarvis.llm.providers.openai")

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIClient(LLMClient):
    """OpenAI API client."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        timeout: int = 120,
    ):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key (or use OPENAI_API_KEY env var)
            model: Model to use (gpt-4o, gpt-4o-mini, gpt-3.5-turbo)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def is_available(self) -> bool:
        """Check if OpenAI API is available."""
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
            return False

        try:
            # Simple models list request to verify API key
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"OpenAI availability check failed: {e}")
            return False

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        **kwargs,
    ) -> str:
        """
        Send a chat message to OpenAI.

        Args:
            messages: List of messages with 'role' and 'content'
            system: Optional system prompt
            **kwargs: Additional options (model, temperature, etc.)

        Returns:
            OpenAI's response
        """
        if not self.api_key:
            raise LLMConnectionError(
                "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
            )

        # Build messages list
        api_messages = []
        if system:
            api_messages.append({"role": "system", "content": system})

        for msg in messages:
            api_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        model = kwargs.get("model", self.model)

        try:
            response = await self._client.post(
                OPENAI_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": api_messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096),
                },
            )

            if response.status_code != 200:
                error_data = response.json()
                raise LLMResponseError(
                    f"OpenAI API error: {error_data.get('error', {}).get('message', 'Unknown error')}"
                )

            data = response.json()
            return data["choices"][0]["message"]["content"]

        except httpx.TimeoutException:
            raise LLMResponseError(f"OpenAI request timed out after {self.timeout}s")
        except httpx.RequestError as e:
            raise LLMConnectionError(f"Failed to connect to OpenAI: {e}")

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        system: str | None = None,
        **kwargs,
    ) -> str:
        """
        Generate a response using OpenAI.

        Args:
            prompt: The prompt to send
            model: Model to use (overrides default)
            system: Optional system prompt
            **kwargs: Additional options

        Returns:
            OpenAI's response
        """
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(
            messages=messages,
            system=system,
            model=model or self.model,
            **kwargs,
        )

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream a chat response from OpenAI.

        Args:
            messages: List of messages
            system: Optional system prompt
            **kwargs: Additional options

        Yields:
            Response chunks
        """
        if not self.api_key:
            raise LLMConnectionError(
                "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
            )

        api_messages = []
        if system:
            api_messages.append({"role": "system", "content": system})

        for msg in messages:
            api_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        model = kwargs.get("model", self.model)

        try:
            async with self._client.stream(
                "POST",
                OPENAI_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": api_messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096),
                    "stream": True,
                },
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            import json
                            chunk = json.loads(data)
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError):
                            continue

        except httpx.TimeoutException:
            raise LLMResponseError(f"OpenAI stream timed out after {self.timeout}s")
        except httpx.RequestError as e:
            raise LLMConnectionError(f"Failed to connect to OpenAI: {e}")

    async def list_models(self) -> list[str]:
        """List available OpenAI models."""
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ]

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()


__all__ = ["OpenAIClient"]
