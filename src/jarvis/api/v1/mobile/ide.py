import os
import subprocess
import platform
from pathlib import Path
from fastapi import APIRouter
from .models import CommandResponse, OpenPathRequest

router = APIRouter()


def _resolve_path(path: str) -> str:
    """Resolve a path, handling relative paths and ~ expansion."""
    # Expand ~ on Unix-like systems
    if path.startswith("~"):
        path = os.path.expanduser(path)

    # Convert to absolute path if relative
    if not os.path.isabs(path):
        path = os.path.abspath(path)

    return path


def _launch_editor(cmd: list[str]) -> CommandResponse:
    """Fire-and-forget launch of an editor. Never blocks waiting for it to exit."""
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        return CommandResponse(status="success", message=f"Launched: {' '.join(cmd)}")
    except FileNotFoundError:
        return CommandResponse(status="error", message=f"Editor not found: {cmd[0]}")
    except Exception as e:
        return CommandResponse(status="error", message=str(e))


@router.post("/vscode/open", response_model=CommandResponse)
async def open_vscode():
    """Launch VS Code."""
    return _launch_editor(["code"])


@router.post("/vscode/open-project", response_model=CommandResponse)
async def open_vscode_project(request: OpenPathRequest):
    """Open a project in VS Code."""
    path = _resolve_path(request.path)
    if not os.path.exists(path):
        return CommandResponse(status="error", message=f"Path not found: {path}")
    return _launch_editor(["code", path])


@router.post("/vscode/open-folder", response_model=CommandResponse)
async def open_vscode_folder(request: OpenPathRequest):
    """Open a folder in a new VS Code window."""
    path = _resolve_path(request.path)
    if not os.path.exists(path):
        return CommandResponse(status="error", message=f"Path not found: {path}")
    if not os.path.isdir(path):
        return CommandResponse(status="error", message=f"Path is not a folder: {path}")
    return _launch_editor(["code", "--new-window", path])


@router.post("/project/open-cursor", response_model=CommandResponse)
async def open_in_cursor(request: OpenPathRequest):
    """Open path in Cursor IDE."""
    path = _resolve_path(request.path)
    if not os.path.exists(path):
        return CommandResponse(status="error", message=f"Path not found: {path}")
    return _launch_editor(["cursor", path])


@router.post("/project/launch", response_model=CommandResponse)
async def launch_project(request: OpenPathRequest):
    """
    Try to launch a project in an IDE, preferring VS Code, then Cursor.
    Returns which editor was successfully opened.
    """
    path = _resolve_path(request.path)
    if not os.path.exists(path):
        return CommandResponse(status="error", message=f"Path not found: {path}")

    # Try VS Code first
    try:
        subprocess.Popen(
            ["code", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        return CommandResponse(status="success", message=f"Opened in VS Code: {path}")
    except FileNotFoundError:
        pass

    # Fall back to Cursor
    try:
        subprocess.Popen(
            ["cursor", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        return CommandResponse(status="success", message=f"Opened in Cursor: {path}")
    except FileNotFoundError:
        pass

    # Neither found
    return CommandResponse(status="error", message="Neither VS Code nor Cursor found on system")
