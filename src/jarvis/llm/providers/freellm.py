
"""
FreeLLM Provider.

Uses FreeLLM API (OpenAI-compatible) for AI assistance.
Works in cloud deployments without local dependencies.
"""

import os
from typing import AsyncIterator

import httpx

from jarvis.llm.client import LLMClient
from jarvis.core.logging import get_logger
from jarvis.core.exceptions import LLMConnectionError, LLMResponseError
from jarvis.config import get_settings

logger = get_logger("jarvis.llm.providers.freellm")


class FreeLLMClient(LLMClient):
    """FreeLLM API client."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "auto",
        timeout: int = 120,
    ):
        """
        Initialize FreeLLM client.

        Args:
            api_key: FreeLLM API key (or use JARVIS_FREELLM_API_KEY env var)
            base_url: FreeLLM API URL (or use JARVIS_FREELLM_API_URL env var)
            model: Model to use (defaults to 'auto')
            timeout: Request timeout in seconds
        """
        settings = get_settings()
        self.api_key = api_key or getattr(settings, "freellm_api_key", "")
        self.base_url = base_url or getattr(settings, "freellm_api_url", "http://localhost:3001/v1")
        if self.base_url.endswith("/"):
            self.base_url = self.base_url[:-1]
        self.api_url = f"{self.base_url}/chat/completions"
        self.models_url = f"{self.base_url}/models"
        self.model = model
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def is_available(self) -> bool:
        """Check if FreeLLM API is available."""
        if not self.api_key:
            logger.warning("FreeLLM API key not configured")
            return False

        try:
            # Simple models list request to verify API key
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    self.models_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"FreeLLM availability check failed: {e}")
            return False

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        **kwargs,
    ) -> str:
        """
        Send a chat message to FreeLLM.
        """
        if not self.api_key:
            raise LLMConnectionError(
                "FreeLLM API key not configured. Set JARVIS_FREELLM_API_KEY environment variable."
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
            response = await self._client.post(
                self.api_url,
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
                    f"FreeLLM API error: {error_data.get('error', {}).get('message', 'Unknown error')}"
                )

            data = response.json()
            return data["choices"][0]["message"]["content"]

        except httpx.TimeoutException:
            raise LLMResponseError(f"FreeLLM request timed out after {self.timeout}s")
        except httpx.RequestError as e:
            raise LLMConnectionError(f"Failed to connect to FreeLLM: {e}")

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        system: str | None = None,
        **kwargs,
    ) -> str:
        """Generate a response using FreeLLM."""
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
        """Stream a chat response from FreeLLM."""
        if not self.api_key:
            raise LLMConnectionError(
                "FreeLLM API key not configured. Set JARVIS_FREELLM_API_KEY environment variable."
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
                self.api_url,
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
            raise LLMResponseError(f"FreeLLM stream timed out after {self.timeout}s")
        except httpx.RequestError as e:
            raise LLMConnectionError(f"Failed to connect to FreeLLM: {e}")

    async def list_models(self) -> list[str]:
        """List available FreeLLM models."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    self.models_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if response.status_code == 200:
                    data = response.json()
                    return [m["id"] for m in data.get("data", [])]
        except Exception:
            pass
        return ["auto"]

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

__all__ = ["FreeLLMClient"]
