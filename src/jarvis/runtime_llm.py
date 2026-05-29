"""
Runtime LLM settings (persisted under ~/.jarvis, applied without server restart).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path.home() / ".jarvis" / "llm_runtime.json"

# Safe default for low-RAM machines
DEFAULT_OLLAMA_MODEL = "llama3.2:1b"

_HEAVY_OLLAMA_MODELS = frozenset({
    "llama3.2",
    "llama3.2:latest",
    "llama3",
    "llama3:latest",
    "llama3.1",
    "llama3.1:8b",
    "llama3:8b",
    "llama3.1:70b",
})


def _load() -> dict[str, Any]:
    try:
        if _CONFIG_PATH.exists():
            return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save(data: dict[str, Any]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_runtime_llm() -> dict[str, Any]:
    return _load()


def get_effective_ollama_model() -> str:
    from jarvis.config import get_settings

    data = _load()
    model = (data.get("ollama_model") or "").strip()
    if model and model not in _HEAVY_OLLAMA_MODELS:
        return model
    env_model = (get_settings().ollama_model or "").strip()
    if env_model and env_model not in _HEAVY_OLLAMA_MODELS:
        return env_model
    return DEFAULT_OLLAMA_MODEL


def get_effective_ollama_host() -> str:
    from jarvis.config import get_settings

    data = _load()
    host = (data.get("ollama_host") or "").strip()
    return host or get_settings().ollama_host or "http://localhost:11434"


def get_effective_ai_provider() -> str | None:
    p = (_load().get("ai_provider") or "").strip().lower()
    return p or None


def set_runtime_ollama(*, host: str | None = None, model: str | None = None) -> dict[str, Any]:
    data = _load()
    if host is not None:
        data["ollama_host"] = host.strip()
    if model is not None:
        data["ollama_model"] = model.strip()
    _save(data)
    return data


def set_runtime_ai_provider(provider: str) -> None:
    data = _load()
    data["ai_provider"] = provider.strip().lower()
    _save(data)


__all__ = [
    "DEFAULT_OLLAMA_MODEL",
    "get_effective_ollama_model",
    "get_effective_ollama_host",
    "get_effective_ai_provider",
    "get_runtime_llm",
    "set_runtime_ollama",
    "set_runtime_ai_provider",
]
