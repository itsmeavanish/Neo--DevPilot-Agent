"""Persist GitHub PAT for Copilot API (survives server restarts)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

_TOKEN_FILE = Path.home() / ".jarvis" / "github_token"
_USERNAME_FILE = Path.home() / ".jarvis" / "github_username"

_token: Optional[str] = None
_username: Optional[str] = None
_loaded = False


def _ensure_loaded() -> None:
    global _token, _username, _loaded
    if _loaded:
        return
    _loaded = True
    try:
        if _TOKEN_FILE.exists():
            _token = _TOKEN_FILE.read_text(encoding="utf-8").strip() or None
        if _USERNAME_FILE.exists():
            _username = _USERNAME_FILE.read_text(encoding="utf-8").strip() or None
    except OSError:
        pass
    if _token:
        try:
            from jarvis.llm.providers.copilot_api import set_copilot_token

            set_copilot_token(_token)
        except ImportError:
            pass


def get_stored_github_token() -> Optional[str]:
    _ensure_loaded()
    return _token


def get_stored_github_username() -> Optional[str]:
    _ensure_loaded()
    return _username


def save_github_token(token: str, username: str) -> None:
    global _token, _username
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(token.strip(), encoding="utf-8")
    _USERNAME_FILE.write_text(username, encoding="utf-8")
    _token = token.strip()
    _username = username
    try:
        from jarvis.llm.providers.copilot_api import set_copilot_token

        set_copilot_token(_token)
    except ImportError:
        pass


def clear_github_token() -> None:
    global _token, _username
    _token = None
    _username = None
    for p in (_TOKEN_FILE, _USERNAME_FILE):
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass


__all__ = [
    "get_stored_github_token",
    "get_stored_github_username",
    "save_github_token",
    "clear_github_token",
]
