import os
import subprocess
import platform
from fastapi import APIRouter
from .models import CommandResponse, OpenPathRequest

router = APIRouter()


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
    path = request.path
    if not os.path.exists(path):
        return CommandResponse(status="error", message=f"Path not found: {path}")
    return _launch_editor(["code", path])


@router.post("/project/open-cursor", response_model=CommandResponse)
async def open_in_cursor(request: OpenPathRequest):
    """Open path in Cursor IDE."""
    path = request.path
    if not os.path.exists(path):
        return CommandResponse(status="error", message=f"Path not found: {path}")
    return _launch_editor(["cursor", path])
