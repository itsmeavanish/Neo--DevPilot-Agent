"""
Ollama LLM Client for JARVIS.

Provides integration with locally-running Ollama models.
"""

import asyncio
import json
from typing import Any, AsyncIterator

import httpx

from jarvis.llm.client import LLMClient, LLMResponse
from jarvis.core.logging import get_logger
from jarvis.core.exceptions import LLMConnectionError, LLMResponseError
from jarvis.core.constants import DEFAULT_LLM_TIMEOUT

logger = get_logger("jarvis.llm.ollama")


class OllamaClient(LLMClient):
    """
    Client for Ollama local LLM server.

    Ollama provides a simple API for running local LLMs.
    Default endpoint: http://localhost:11434
    """

    DEFAULT_HOST = "http://localhost:11434"
    DEFAULT_MODEL = "llama3.2"  # Default model

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        timeout: int = DEFAULT_LLM_TIMEOUT,
        **default_options,
    ):
        """
        Initialize Ollama client.

        Args:
            host: Ollama server URL (default: http://localhost:11434)
            model: Default model to use (default: llama3.2)
            timeout: Request timeout in seconds
            **default_options: Default generation options (temperature, etc.)
        """
        self.host = (host or self.DEFAULT_HOST).rstrip("/")
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout
        self.default_options = default_options

        self.logger = get_logger("jarvis.llm.ollama")

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        model: str | None = None,
        **kwargs,
    ) -> str:
        """
        Send a chat message and get a response.

        Args:
            messages: List of messages with 'role' and 'content'
            system: Optional system prompt
            model: Model to use (overrides default)
            **kwargs: Additional options (temperature, top_p, etc.)

        Returns:
            The assistant's response content
        """
        model = model or self.model

        # Build messages list with system prompt
        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        # Merge options
        options = {**self.default_options, **kwargs}

        payload = {
            "model": model,
            "messages": chat_messages,
            "stream": False,
            "options": options,
        }

        self.logger.debug(f"Sending chat request to {model}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.host}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                content = data.get("message", {}).get("content", "")
                self.logger.debug(f"Received response: {len(content)} chars")
                return content

        except httpx.ConnectError:
            raise LLMConnectionError(
                f"Cannot connect to Ollama at {self.host}. "
                "Make sure Ollama is running (ollama serve)"
            )
        except httpx.TimeoutException:
            raise LLMConnectionError(f"Request to Ollama timed out after {self.timeout}s")
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = error_data.get("error", "")
            except Exception:
                error_detail = e.response.text[:200] if e.response.text else ""

            if status_code == 500:
                if "model" in error_detail.lower() and "not found" in error_detail.lower():
                    raise LLMResponseError(
                        f"Model '{model}' not found. Run 'ollama pull {model}' to download it."
                    )
                elif "out of memory" in error_detail.lower():
                    raise LLMResponseError(
                        "Ollama ran out of memory. Try a smaller model or free up system memory."
                    )
                else:
                    raise LLMResponseError(
                        f"Ollama server error (500): {error_detail or 'Unknown error'}. "
                        "Check if Ollama is running properly and the model is loaded."
                    )
            elif status_code == 404:
                raise LLMResponseError(
                    f"Model '{model}' not found. Run 'ollama pull {model}' to download it."
                )
            else:
                raise LLMResponseError(
                    f"Ollama returned error {status_code}: {error_detail or 'Unknown error'}"
                )
        except Exception as e:
            raise LLMResponseError(f"Unexpected error from Ollama: {e}")

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        model: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Send a chat message and stream the response.

        Args:
            messages: List of messages with 'role' and 'content'
            system: Optional system prompt
            model: Model to use (overrides default)
            **kwargs: Additional options

        Yields:
            Chunks of the assistant's response
        """
        model = model or self.model

        # Build messages list with system prompt
        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        # Merge options
        options = {**self.default_options, **kwargs}

        payload = {
            "model": model,
            "messages": chat_messages,
            "stream": True,
            "options": options,
        }

        self.logger.debug(f"Starting streaming chat with {model}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.host}/api/chat",
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                content = data.get("message", {}).get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue

        except httpx.ConnectError:
            raise LLMConnectionError(
                f"Cannot connect to Ollama at {self.host}. "
                "Make sure Ollama is running."
            )
        except httpx.TimeoutException:
            raise LLMConnectionError(f"Stream timed out after {self.timeout}s")

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        system: str | None = None,
        **kwargs,
    ) -> str:
        """
        Generate a completion (non-chat mode).

        Args:
            prompt: The prompt to complete
            model: Model to use
            system: Optional system prompt
            **kwargs: Additional options

        Returns:
            The generated text
        """
        model = model or self.model
        options = {**self.default_options, **kwargs}

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }

        # Add system prompt if provided
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.host}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")

        except httpx.ConnectError:
            raise LLMConnectionError(
                f"Cannot connect to Ollama at {self.host}. "
                "Make sure Ollama is running (ollama serve)"
            )
        except httpx.TimeoutException:
            raise LLMConnectionError(f"Request to Ollama timed out after {self.timeout}s")
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = error_data.get("error", "")
            except Exception:
                error_detail = e.response.text[:200] if e.response.text else ""

            if status_code == 500:
                # Common 500 error causes
                if "model" in error_detail.lower() and "not found" in error_detail.lower():
                    raise LLMResponseError(
                        f"Model '{model}' not found. Run 'ollama pull {model}' to download it."
                    )
                elif "out of memory" in error_detail.lower():
                    raise LLMResponseError(
                        "Ollama ran out of memory. Try a smaller model or free up system memory."
                    )
                else:
                    raise LLMResponseError(
                        f"Ollama server error (500): {error_detail or 'Unknown error'}. "
                        "Check if Ollama is running properly and the model is loaded."
                    )
            elif status_code == 404:
                raise LLMResponseError(
                    f"Model '{model}' not found. Run 'ollama pull {model}' to download it."
                )
            else:
                raise LLMResponseError(
                    f"Ollama returned error {status_code}: {error_detail or 'Unknown error'}"
                )
        except Exception as e:
            raise LLMResponseError(f"Generation failed: {e}")

    async def embed(
        self,
        text: str,
        model: str = "nomic-embed-text",
    ) -> list[float]:
        """
        Generate embeddings for text.

        Args:
            text: Text to embed
            model: Embedding model (default: nomic-embed-text)

        Returns:
            Embedding vector as list of floats
        """
        payload = {
            "model": model,
            "prompt": text,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.host}/api/embeddings",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("embedding", [])

        except httpx.ConnectError:
            raise LLMConnectionError(f"Cannot connect to Ollama at {self.host}")
        except Exception as e:
            raise LLMResponseError(f"Embedding failed: {e}")

    async def is_available(self) -> bool:
        """Check if Ollama server is available."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.host}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List available models."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.host}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            self.logger.warning(f"Failed to list models: {e}")
            return []

    async def pull_model(self, model: str) -> bool:
        """
        Pull a model from Ollama registry.

        Args:
            model: Model name to pull

        Returns:
            True if successful
        """
        payload = {"name": model}

        try:
            async with httpx.AsyncClient(timeout=600) as client:  # Long timeout for download
                async with client.stream(
                    "POST",
                    f"{self.host}/api/pull",
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            data = json.loads(line)
                            status = data.get("status", "")
                            self.logger.info(f"Pull {model}: {status}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to pull model {model}: {e}")
            return False


__all__ = ["OllamaClient"]
