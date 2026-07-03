"""
Unified AI chat via FreeLLM provider.

Supports both full-response and streaming modes.
"""

from __future__ import annotations

from typing import AsyncIterator, Optional

from jarvis.core.logging import get_logger
from jarvis.core.exceptions import LLMConnectionError

logger = get_logger("jarvis.llm.ai_service")


async def _try_freellm(prompt: str, system: str) -> tuple[bool, str]:
    from jarvis.config import get_settings

    settings = get_settings()
    if not getattr(settings, "freellm_api_key", None):
        return False, "FreeLLM API key not configured"
    try:
        from jarvis.llm.providers.freellm import FreeLLMClient

        client = FreeLLMClient(api_key=settings.freellm_api_key, base_url=getattr(settings, "freellm_api_url", "http://localhost:3001/v1"))
        if not await client.is_available():
            return False, "FreeLLM API unavailable or key invalid"
        text = await client.generate(prompt=prompt, system=system)
        return True, text
    except Exception as e:
        return False, str(e)


async def generate_chat(
    prompt: str,
    *,
    system: str = "You are a helpful AI coding assistant. Provide clear, concise answers.",
    code_context: Optional[str] = None,
    preferred_provider: str = "freellm",
) -> tuple[str, str, list[str]]:
    """
    Returns (status, text_or_error, providers_tried).
    status is 'success' or 'error'.
    """
    full_prompt = prompt
    if code_context:
        full_prompt = f"Code context:\n\n```\n{code_context}\n```\n\nQuestion: {prompt}"

    ok, text = await _try_freellm(full_prompt, system)
    if ok:
        return "success", text, []

    hint = (
        "FreeLLM provider could not answer.\n\n"
        "Make sure FreeLLM API key is configured in Settings.\n\n"
        f"Error: {text}"
    )
    return "error", hint, [f"freellm: {text}"]


async def generate_chat_stream(
    prompt: str,
    *,
    system: str = "You are a helpful AI coding assistant. Provide clear, concise answers.",
    code_context: Optional[str] = None,
    preferred_provider: str = "freellm",
    messages: Optional[list[dict[str, str]]] = None,
    model_override: Optional[str] = None,
) -> AsyncIterator[str]:
    """
    Streaming version of generate_chat. Yields text chunks as they arrive.
    """
    from jarvis.config import get_settings
    from jarvis.llm.providers.freellm import FreeLLMClient

    full_prompt = prompt
    if code_context:
        full_prompt = f"Code context:\n\n```\n{code_context}\n```\n\nQuestion: {prompt}"

    chat_messages = []
    if messages:
        chat_messages.extend(messages)
    chat_messages.append({"role": "user", "content": full_prompt})

    settings = get_settings()
    if not getattr(settings, "freellm_api_key", None):
        yield "FreeLLM API key not configured. Go to Settings to configure it."
        return

    client = FreeLLMClient(
        api_key=settings.freellm_api_key,
        base_url=getattr(settings, "freellm_api_url", "http://localhost:3001/v1"),
    )
    if not await client.is_available():
        yield "FreeLLM API unavailable. Check your API key and server URL."
        return

    kwargs = {}
    if model_override:
        kwargs["model"] = model_override

    try:
        async for chunk in client.chat_stream(messages=chat_messages, system=system, **kwargs):
            yield chunk
    except Exception as e:
        yield f"\n\nFreeLLM streaming error: {e}"


async def get_streaming_llm_client(
    preferred_provider: str = "freellm", model: Optional[str] = None
):
    """
    Get a FreeLLM client for the ReAct agent loop.
    """
    from jarvis.config import get_settings
    from jarvis.llm.providers.freellm import FreeLLMClient

    settings = get_settings()
    if not getattr(settings, "freellm_api_key", None):
        return None

    client = FreeLLMClient(
        api_key=settings.freellm_api_key,
        base_url=getattr(settings, "freellm_api_url", "http://localhost:3001/v1"),
        model=model or "auto",
    )
    if await client.is_available():
        return client
    return None


__all__ = [
    "generate_chat",
    "generate_chat_stream",
    "get_streaming_llm_client",
]
