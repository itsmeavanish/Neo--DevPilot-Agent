"""
Gemini Client for JARVIS.

Provides integration with Google's Gemini models using the official google-genai SDK.
"""

import json
from typing import AsyncIterator

from google import genai
from google.genai import types
from google.genai.errors import APIError

from jarvis.core.exceptions import LLMConnectionError, LLMResponseError
from jarvis.core.logging import get_logger
from jarvis.llm.client import LLMClient
from jarvis.config import get_settings

logger = get_logger("jarvis.llm.providers.gemini")

class GeminiClient(LLMClient):
    """Client for Google Gemini API."""

    def __init__(self, **kwargs):
        """Initialize the Gemini client."""
        settings = get_settings()
        self.api_key = kwargs.get("api_key") or getattr(settings, "gemini_api_key", None)
        self.model = kwargs.get("model") or getattr(settings, "gemini_model", "gemini-2.5-flash")

        if not self.api_key:
            logger.warning("Gemini API key not configured. Set JARVIS_GEMINI_API_KEY environment variable.")

        # Initialize the official client
        if self.api_key:
            self._client = genai.Client(api_key=self.api_key)
        else:
            self._client = None

    def _convert_messages(self, messages: list[dict[str, str]]) -> list[types.Content]:
        """Convert standard messages to Gemini Content objects."""
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            # Gemini roles are 'user' and 'model'
            gemini_role = "model" if role == "assistant" else "user"

            # Skip system messages here as they are passed via config
            if role == "system":
                continue

            contents.append(
                types.Content(
                    role=gemini_role,
                    parts=[types.Part.from_text(msg.get("content", ""))]
                )
            )
        return contents

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        **kwargs,
    ) -> str:
        """
        Send a chat message and get a response.
        """
        if not self._client:
            raise LLMConnectionError("Gemini client not initialized (missing API key).")

        model = kwargs.get("model", self.model)

        try:
            contents = self._convert_messages(messages)

            config_kwargs = {
                "temperature": kwargs.get("temperature", 0.7),
            }
            if system:
                config_kwargs["system_instruction"] = system

            config = types.GenerateContentConfig(**config_kwargs)

            # Use generate_content asynchronously
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            if response.text:
                return response.text
            return ""

        except APIError as e:
            raise LLMConnectionError(f"Gemini API error: {e}")
        except Exception as e:
            raise LLMResponseError(f"Error communicating with Gemini: {e}")

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream a chat response from Gemini.
        """
        if not self._client:
            raise LLMConnectionError("Gemini client not initialized (missing API key).")

        model = kwargs.get("model", self.model)

        try:
            contents = self._convert_messages(messages)

            config_kwargs = {
                "temperature": kwargs.get("temperature", 0.7),
            }
            if system:
                config_kwargs["system_instruction"] = system

            config = types.GenerateContentConfig(**config_kwargs)

            async for chunk in await self._client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    yield chunk.text

        except APIError as e:
            raise LLMConnectionError(f"Gemini API error during stream: {e}")
        except Exception as e:
            raise LLMResponseError(f"Error streaming from Gemini: {e}")

    async def is_available(self) -> bool:
        """Check if Gemini is configured and available."""
        if not self.api_key:
            return False

        try:
            # Quick check if the API is reachable
            await self.list_models()
            return True
        except Exception as e:
            logger.debug(f"Gemini availability check failed: {e}")
            return False

    async def list_models(self) -> list[str]:
        """List available models."""
        if not self._client:
            return []

        try:
            # We iterate through models using async support in genai SDK if possible
            # or fallback to list of known models if direct iteration isn't straightforward
            models = []
            async for m in await self._client.aio.models.list():
                if m.name:
                    models.append(m.name)
            return models
        except Exception as e:
            logger.warning(f"Failed to list Gemini models: {e}")
            return ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-pro", "gemini-1.5-flash"]
