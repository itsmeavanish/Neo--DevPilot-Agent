"""
IDE API endpoints.

Endpoints for IDE integration and code intelligence features.
"""

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from jarvis.ide.manager import get_ide_manager
from jarvis.ide.models import IDEType, FileEdit, TextEdit, Range, Position

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════

class OpenFileRequest(BaseModel):
    """Request to open a file."""
    path: str = Field(..., description="File path to open")
    line: int | None = Field(default=None, description="Line number to go to")
    column: int | None = Field(default=None, description="Column number")


class EditRequest(BaseModel):
    """Request to edit a file."""
    path: str = Field(..., description="File path")
    edits: list[dict] = Field(..., description="List of edits")
    create_if_missing: bool = Field(default=False, description="Create file if it doesn't exist")


class InsertRequest(BaseModel):
    """Request to insert text."""
    path: str = Field(..., description="File path")
    line: int = Field(..., description="Line number (0-indexed)")
    column: int = Field(..., description="Column number (0-indexed)")
    text: str = Field(..., description="Text to insert")


class ReplaceRequest(BaseModel):
    """Request to replace text."""
    path: str = Field(..., description="File path")
    start_line: int = Field(..., description="Start line (0-indexed)")
    start_column: int = Field(..., description="Start column (0-indexed)")
    end_line: int = Field(..., description="End line (0-indexed)")
    end_column: int = Field(..., description="End column (0-indexed)")
    new_text: str = Field(..., description="Replacement text")


class CommandRequest(BaseModel):
    """Request to execute IDE command."""
    command: str = Field(..., description="Command name")
    args: list[Any] = Field(default_factory=list, description="Command arguments")


class TerminalRequest(BaseModel):
    """Request to run in terminal."""
    command: str = Field(..., description="Command to run")
    name: str | None = Field(default=None, description="Terminal name")


class DiagnosticResponse(BaseModel):
    """Diagnostic information."""
    id: str
    file_path: str
    severity: str
    message: str
    source: str
    code: str | None
    location: str
    range: dict | None


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def get_manager():
    return get_ide_manager()


# ═══════════════════════════════════════════════════════════════
# IDE Status Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/adapters")
async def list_adapters():
    """
    List all available IDE adapters.
    """
    manager = get_manager()
    available = manager.list_available()
    active = manager.active_adapter

    return {
        "adapters": [ide.value for ide in available],
        "active": active.ide_type.value if active else None,
    }


@router.get("/status")
async def get_ide_status():
    """
    Get IDE integration status.
    """
    manager = get_manager()

    available = manager.list_available()
    active = manager.active_adapter

    return {
        "available_ides": [ide.value for ide in available],
        "active_ide": active.ide_type.value if active else None,
        "connected": active.connected if active else False,
    }


@router.post("/connect")
async def connect_ide(ide_type: str | None = Query(default=None)):
    """
    Connect to an IDE.
    """
    manager = get_manager()

    if ide_type:
        try:
            ide = IDEType(ide_type)
            if not manager.set_active(ide):
                raise HTTPException(status_code=404, detail=f"IDE not available: {ide_type}")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid IDE type: {ide_type}")

    success = await manager.connect()

    return {
        "connected": success,
        "ide": manager.active_adapter.ide_type.value if manager.active_adapter else None,
    }


@router.get("/workspace")
async def get_workspace():
    """
    Get workspace information.
    """
    manager = get_manager()
    workspace = await manager.get_workspace_info()

    if not workspace:
        raise HTTPException(status_code=404, detail="No workspace information available")

    return workspace.to_dict()


# ═══════════════════════════════════════════════════════════════
# File Operations Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/files/open")
async def open_file(request: OpenFileRequest):
    """
    Open a file in the IDE.
    """
    manager = get_manager()

    success = await manager.open_file(
        request.path,
        request.line,
        request.column,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to open file")

    return {"opened": request.path}


@router.post("/files/edit")
async def edit_file(request: EditRequest):
    """
    Apply edits to a file.
    """
    manager = get_manager()

    # Convert request to FileEdit
    edits = []
    for edit_data in request.edits:
        range_data = edit_data.get("range", {})
        edits.append(TextEdit(
            range=Range(
                start=Position(
                    range_data.get("start", {}).get("line", 0),
                    range_data.get("start", {}).get("character", 0),
                ),
                end=Position(
                    range_data.get("end", {}).get("line", 0),
                    range_data.get("end", {}).get("character", 0),
                ),
            ),
            new_text=edit_data.get("new_text", ""),
        ))

    file_edit = FileEdit(
        file_path=request.path,
        edits=edits,
        create_if_missing=request.create_if_missing,
    )

    success = await manager.apply_edit(file_edit)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to apply edits")

    return {"edited": request.path, "edit_count": len(edits)}


@router.post("/files/insert")
async def insert_text(request: InsertRequest):
    """
    Insert text at a position.
    """
    manager = get_manager()

    success = await manager.insert_text(
        request.path,
        request.line,
        request.column,
        request.text,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to insert text")

    return {"inserted": True}


@router.post("/files/replace")
async def replace_text(request: ReplaceRequest):
    """
    Replace text in a range.
    """
    manager = get_manager()

    success = await manager.replace_text(
        request.path,
        request.start_line,
        request.start_column,
        request.end_line,
        request.end_column,
        request.new_text,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to replace text")

    return {"replaced": True}


# ═══════════════════════════════════════════════════════════════
# Diagnostics Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/diagnostics", response_model=list[DiagnosticResponse])
async def get_diagnostics(
    path: str | None = Query(default=None, description="Filter by file path"),
    severity: str | None = Query(default=None, description="Filter by severity"),
):
    """
    Get diagnostics (errors, warnings) from the IDE.
    """
    manager = get_manager()
    diagnostics = await manager.get_diagnostics(path)

    if severity:
        diagnostics = [d for d in diagnostics if d.severity.value == severity]

    return [d.to_dict() for d in diagnostics]


@router.get("/diagnostics/errors", response_model=list[DiagnosticResponse])
async def get_errors():
    """
    Get all error-level diagnostics.
    """
    manager = get_manager()
    errors = await manager.get_all_errors()
    return [e.to_dict() for e in errors]


@router.get("/diagnostics/warnings", response_model=list[DiagnosticResponse])
async def get_warnings():
    """
    Get all warning-level diagnostics.
    """
    manager = get_manager()
    warnings = await manager.get_all_warnings()
    return [w.to_dict() for w in warnings]


@router.post("/diagnostics/{diagnostic_id}/goto")
async def goto_diagnostic(diagnostic_id: str):
    """
    Navigate to a diagnostic location.
    """
    manager = get_manager()
    diagnostics = await manager.get_diagnostics()

    diagnostic = next((d for d in diagnostics if d.id == diagnostic_id), None)
    if not diagnostic:
        raise HTTPException(status_code=404, detail="Diagnostic not found")

    success = await manager.goto_error(diagnostic)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to navigate to diagnostic")

    return {"navigated": diagnostic.location_string}


# ═══════════════════════════════════════════════════════════════
# Command Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/commands/execute")
async def execute_command(request: CommandRequest):
    """
    Execute an IDE command.
    """
    manager = get_manager()
    result = await manager.execute_command(request.command, request.args)

    return {"executed": request.command, "result": result}


@router.get("/commands")
async def list_commands():
    """
    List available IDE commands.
    """
    manager = get_manager()

    if not manager.active_adapter:
        return {"commands": []}

    commands = await manager.active_adapter.get_available_commands()
    return {"commands": commands}


# ═══════════════════════════════════════════════════════════════
# Terminal Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/terminal/run")
async def run_in_terminal(request: TerminalRequest):
    """
    Run a command in the IDE's integrated terminal.
    """
    manager = get_manager()

    success = await manager.run_in_terminal(request.command, request.name)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to run in terminal")

    return {"running": request.command}


# ═══════════════════════════════════════════════════════════════
# Message Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/message")
async def show_message(
    message: str = Query(..., description="Message to show"),
    level: str = Query(default="info", description="Message level"),
):
    """
    Show a message in the IDE.
    """
    manager = get_manager()
    await manager.show_message(message, level)

    return {"shown": True}


__all__ = ["router"]
