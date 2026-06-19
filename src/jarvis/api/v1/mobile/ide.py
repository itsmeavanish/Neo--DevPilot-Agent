import os
import platform
from fastapi import APIRouter
from .models import CommandResponse, OpenPathRequest
from .utils import run_command

router = APIRouter()

@router.post("/vscode/open", response_model=CommandResponse)
async def open_vscode():
    """Launch VS Code."""
    if platform.system() == "Windows":
        cmd = "code"
    else:
        cmd = "code"
    return await run_command(cmd)

@router.post("/vscode/open-project", response_model=CommandResponse)
async def open_vscode_project(request: OpenPathRequest):
    """Open a project in VS Code."""
    path = request.path
    if not os.path.exists(path):
        return CommandResponse(status="error", message=f"Path not found: {path}")
    cmd = f'code "{path}"'
    return await run_command(cmd)

@router.post("/project/open-cursor", response_model=CommandResponse)
async def open_in_cursor(request: OpenPathRequest):
    """Open path in Cursor IDE."""
    path = request.path
    if not os.path.exists(path):
        return CommandResponse(status="error", message=f"Path not found: {path}")
    cmd = f'cursor "{path}"'
    return await run_command(cmd)
