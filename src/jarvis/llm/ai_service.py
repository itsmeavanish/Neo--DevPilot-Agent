"""
Unified AI chat with provider fallback for mobile / IDE.

Tries cloud/token providers before local Ollama so chat works even when Ollama OOMs.
"""

from __future__ import annotations

from typing import Optional

from jarvis.runtime_llm import (
    DEFAULT_OLLAMA_MODEL,
    get_effective_ollama_host,
    get_effective_ollama_model,
)
from jarvis.core.logging import get_logger
from jarvis.core.exceptions import LLMConnectionError, LLMResponseError

logger = get_logger("jarvis.llm.ai_service")

# Smaller models tried when the configured Ollama model fails (OOM or missing)
OLLAMA_FALLBACK_MODELS = (
    "llama3.2:1b",
    "phi3:mini",
    "gemma2:2b",
    "tinyllama",
    "qwen2.5:0.5b",
)

# Low-memory generation options passed to Ollama
OLLAMA_LOW_MEM_OPTIONS = {
    "num_ctx": 2048,
    "num_predict": 1024,
}


def _is_oom_message(msg: str) -> bool:
    low = (msg or "").lower()
    return "out of memory" in low or "oom" in low or "cudamalloc" in low or "allocate" in low and "memory" in low


async def _try_ollama(prompt: str, system: str, model: str) -> tuple[bool, str]:
    from jarvis.llm.providers.ollama import OllamaClient

    host = get_effective_ollama_host()
    client = OllamaClient(host=host, model=model)
    if not await client.is_available():
        return False, "Ollama is not running. Start it with: ollama serve"
    try:
        text = await client.generate(
            prompt=prompt,
            model=model,
            system=system,
            **OLLAMA_LOW_MEM_OPTIONS,
        )
        return True, text
    except LLMResponseError as e:
        msg = str(e)
        if _is_oom_message(msg):
            return False, f"OOM:{model}"
        return False, msg
    except LLMConnectionError as e:
        return False, str(e)
    except Exception as e:
        msg = str(e)
        if _is_oom_message(msg):
            return False, f"OOM:{model}"
        return False, msg


async def _try_ollama_with_fallbacks(prompt: str, system: str) -> tuple[bool, str]:
    primary = get_effective_ollama_model()
    candidates: list[str] = []
    for m in [primary, *OLLAMA_FALLBACK_MODELS]:
        if m and m not in candidates:
            candidates.append(m)

    last_oom = False
    errors: list[str] = []

    for model in candidates:
        ok, out = await _try_ollama(prompt, system, model)
        if ok:
            if model != primary:
                return True, (
                    f"(Using `{model}` — `{primary}` was unavailable or out of memory.)\n\n{out}"
                )
            return True, out
        errors.append(f"{model}: {out[:120]}")
        if out.startswith("OOM:") or _is_oom_message(out):
            last_oom = True
            continue
        # Model missing etc. — try next candidate
        logger.debug("Ollama model %s failed: %s", model, out)

    if last_oom:
        return (
            False,
            "All tried Ollama models ran out of memory. "
            f"On the PC run: ollama pull {DEFAULT_OLLAMA_MODEL} "
            "then Settings → Ollama → set model to llama3.2:1b. "
            "Or add GitHub/OpenAI in Settings for cloud AI.",
        )
    return False, "Ollama failed. " + "; ".join(errors[:3])


async def _try_copilot_cli(prompt: str, system: str, context: Optional[str]) -> tuple[bool, str]:
    try:
        from jarvis.llm.providers.copilot_cli import get_copilot_cli

        cli = get_copilot_cli()
        ok, msg = await cli.check_available()
        if not ok:
            return False, msg
        text = await cli.chat(prompt=prompt, context=context, system_prompt=system)
        if text.startswith("Error:"):
            return False, text
        return True, text
    except Exception as e:
        return False, str(e)


async def _try_freellm(prompt: str, system: str) -> tuple[bool, str]:
    from jarvis.config import get_settings

    settings = get_settings()
    if not getattr(settings, "freellm_api_key", None):
        return False, "FreeLLM API key not configured"
    try:
        from jarvis.llm.providers.freellm import FreeLLMClient

        client = FreeLLMClient(api_key=settings.freellm_api_key, base_url=getattr(settings, "freellm_api_url", "http://localhost:3001/v1"))
        if not await client.is_available():
            return False, "FreeLLM API key invalid or expired"
        text = await client.generate(prompt=prompt, system=system)
        return True, text
    except Exception as e:
        return False, str(e)


def _has_freellm() -> bool:
    from jarvis.config import get_settings

    return bool((getattr(get_settings(), "freellm_api_key", "") or "").strip())


def _provider_chain(preferred: str, has_github_token: bool, has_freellm: bool) -> list[str]:
    """
    Build provider try-order. Cloud/token providers run before Ollama so OOM does not block chat.
    """
    preferred = (preferred or "auto").lower()

    cloud_first = []
    if has_freellm:
        cloud_first.append("freellm")
    cloud_first.extend(["copilot_cli"])

    if preferred == "freellm" and has_freellm:
        chain = ["freellm", *cloud_first, "ollama"]
    elif preferred == "copilot":
        chain = ["copilot_cli", "freellm", "ollama"]
    elif preferred == "ollama":
        # User asked for Ollama but still try cloud first if configured
        chain = [*cloud_first, "ollama"] if cloud_first else ["ollama", *cloud_first]
    else:
        # auto
        chain = [*cloud_first, "ollama"]

    seen: set[str] = set()
    out: list[str] = []
    for p in chain:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


async def generate_chat(
    prompt: str,
    *,
    system: str = "You are a helpful AI coding assistant. Provide clear, concise answers.",
    code_context: Optional[str] = None,
    preferred_provider: str = "auto",
) -> tuple[str, str, list[str]]:
    """
    Returns (status, text_or_error, providers_tried).
    status is 'success' or 'error'.
    """
    from jarvis.auth.github_token_store import get_stored_github_token

    full_prompt = prompt
    if code_context:
        full_prompt = f"Code context:\n\n```\n{code_context}\n```\n\nQuestion: {prompt}"

    has_token = bool(get_stored_github_token())
    has_freellm = _has_freellm()
    chain = _provider_chain(preferred_provider, has_token, has_freellm)
    errors: list[str] = []

    for name in chain:
        try:
            if name in ("copilot_cli", "copilot"):
                ok, text = await _try_copilot_cli(full_prompt, system, code_context)
            elif name == "freellm":
                ok, text = await _try_freellm(full_prompt, system)
            elif name == "ollama":
                ok, text = await _try_ollama_with_fallbacks(full_prompt, system)
            else:
                continue

            if ok:
                return "success", text, errors

            errors.append(f"{name}: {text}")
            logger.info("AI provider %s failed: %s", name, text[:200])
        except Exception as e:
            errors.append(f"{name}: {e}")
            logger.warning("AI provider %s exception: %s", name, e)

    hint = (
        "No AI provider could answer.\n\n"
        "Quick fix (pick one):\n"
        "1. Settings → GitHub → paste Personal Access Token (Copilot)\n"
        "2. Settings → FreeLLM → API key\n"
        "3. On PC: ollama pull llama3.2:1b → Settings → Ollama model llama3.2:1b\n\n"
        "Details:\n" + "\n".join(errors[-5:])
    )
    return "error", hint, errors


__all__ = ["generate_chat", "OLLAMA_FALLBACK_MODELS", "DEFAULT_OLLAMA_MODEL"]
