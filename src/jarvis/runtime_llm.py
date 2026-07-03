"""
Runtime LLM settings (persisted under ~/.jarvis, applied without server restart).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path.home() / ".jarvis" / "llm_runtime.json"


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
    try:
        from jarvis.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass


def get_runtime_llm() -> dict[str, Any]:
    return _load()


def get_effective_ai_provider() -> str | None:
    p = (_load().get("ai_provider") or "").strip().lower()
    return p or "freellm"


def set_runtime_ai_provider(provider: str) -> None:
    data = _load()
    data["ai_provider"] = provider.strip().lower()
    _save(data)


__all__ = [
    "get_effective_ai_provider",
    "get_runtime_llm",
    "set_runtime_ai_provider",
]
