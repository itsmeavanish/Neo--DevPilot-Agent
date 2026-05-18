"""
Request-scoped execution context for paired (remote agent) operations.

Tools read pairing_code from context vars so the executor API stays unchanged.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncIterator

_pairing_code: ContextVar[str | None] = ContextVar("jarvis_pairing_code", default=None)
_capabilities: ContextVar[frozenset[str] | None] = ContextVar("jarvis_capabilities", default=None)
_workspace_root: ContextVar[str | None] = ContextVar("jarvis_workspace_root", default=None)


def get_pairing_code() -> str | None:
    return _pairing_code.get()


def get_workspace_root() -> str | None:
    return _workspace_root.get()


def get_capabilities() -> frozenset[str]:
    caps = _capabilities.get()
    if caps is None:
        return frozenset({"shell", "read_fs", "write_fs", "git", "network"})
    return caps


def set_pairing_context(
    code: str | None,
    capabilities: list[str] | None = None,
    workspace_root: str | None = None,
) -> tuple:
    """Returns reset tokens for clear_pairing_context."""
    c = code.strip().upper() if code else None
    caps: frozenset[str] | None
    if capabilities:
        caps = frozenset(str(x).strip().lower() for x in capabilities if str(x).strip())
    else:
        caps = None
    ws = (workspace_root or "").strip() or None
    return (_pairing_code.set(c), _capabilities.set(caps), _workspace_root.set(ws))


def clear_pairing_context(tokens: tuple) -> None:
    _pairing_code.reset(tokens[0])
    _capabilities.reset(tokens[1])
    if len(tokens) > 2:
        _workspace_root.reset(tokens[2])


@asynccontextmanager
async def pairing_scope(
    code: str | None,
    capabilities: list[str] | None = None,
    workspace_root: str | None = None,
) -> AsyncIterator[None]:
    if not code or not code.strip():
        yield
        return
    tokens = set_pairing_context(code, capabilities, workspace_root)
    try:
        yield
    finally:
        clear_pairing_context(tokens)


def workspace_from_context(ctx: dict | None) -> str | None:
    """Pick workspace root from an execution context dict."""
    if not ctx:
        return None
    for key in ("workspace_root", "cwd", "project_root"):
        val = ctx.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return None


__all__ = [
    "get_pairing_code",
    "get_workspace_root",
    "get_capabilities",
    "set_pairing_context",
    "clear_pairing_context",
    "pairing_scope",
    "workspace_from_context",
]
