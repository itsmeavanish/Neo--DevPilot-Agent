"""
Resolve user paths for paired (remote) filesystem tools under an optional workspace root.
"""

from __future__ import annotations

import os
from pathlib import Path

_BLOCKED_PREFIXES = (
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/var",
    "/sys",
    "/proc",
    "c:\\windows",
    "c:\\program files",
    "c:\\program files (x86)",
)


def resolve_paired_path(user_path: str, workspace_root: str | None) -> tuple[str | None, str | None]:
    """
    Resolve a path for remote agent FS operations.

    Returns (absolute_path, error_message). On success error is None.
    """
    raw = (user_path or "").strip()
    if not raw:
        return None, "path is required"

    path = Path(raw).expanduser()

    if workspace_root:
        root = Path(workspace_root).expanduser()
        try:
            root = root.resolve()
        except OSError:
            return None, f"Invalid workspace root: {workspace_root}"

        if not root.is_dir():
            return None, f"Workspace root is not a directory: {root}"

        if not path.is_absolute():
            path = root / path
        try:
            path = path.resolve()
        except OSError as e:
            return None, str(e)

        try:
            path.relative_to(root)
        except ValueError:
            return None, f"Path must stay inside workspace: {root}"
    else:
        try:
            path = path.resolve()
        except OSError:
            pass

    blocked = _path_blocked(str(path))
    if blocked:
        return None, blocked

    return str(path), None


def _path_blocked(resolved: str) -> str | None:
    norm = os.path.normcase(os.path.normpath(resolved))
    for prefix in _BLOCKED_PREFIXES:
        if norm.startswith(os.path.normcase(prefix)):
            return f"Access denied: protected path ({prefix})"
    return None


__all__ = ["resolve_paired_path"]
