"""
Filesystem tools on the WebSocket-paired laptop agent.
"""

from __future__ import annotations

from typing import Any, ClassVar

from jarvis.core.constants import RiskLevel
from jarvis.core.logging import get_logger
from jarvis.devices.agent_registry import get_agent_registry
from jarvis.execution_context import get_capabilities, get_pairing_code, get_workspace_root
from jarvis.security.audit import audit_log
from jarvis.security.policy import Capability
from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.builtin.paired_path import resolve_paired_path
from jarvis.tools.registry import tool_registry

logger = get_logger("jarvis.tools.paired_fs")


def _require_capability(cap: Capability) -> str | None:
    if cap.value not in get_capabilities():
        return f"Capability '{cap.value}' not granted for this run"
    return None


def _resolve_or_fail(user_path: str) -> tuple[str | None, str | None]:
    resolved, err = resolve_paired_path(user_path, get_workspace_root())
    return resolved, err


async def _agent_fs(code: str, payload: dict[str, Any], wait_timeout: int = 120) -> dict[str, Any]:
    registry = get_agent_registry()
    return await registry.send_agent_request(code, payload, wait_timeout=wait_timeout)


@tool_registry.register
class PairedReadFileTool(BaseTool):
    """Read a text file on the paired laptop."""

    name: ClassVar[str] = "paired_read_file"
    description: ClassVar[str] = (
        "Read a file on the paired remote laptop. Use paths relative to workspace_root when set."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.LOW
    timeout: ClassVar[int] = 120

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path on the paired laptop"},
            "max_lines": {"type": "integer", "minimum": 1, "maximum": 50000},
        },
        "required": ["path"],
    }

    async def execute(self, params: dict) -> ToolResult:
        cap_err = _require_capability(Capability.READ_FS)
        if cap_err:
            return ToolResult.failure(cap_err)

        code = get_pairing_code()
        if not code:
            return ToolResult.failure("No pairing context: run via Mission/Autonomous with a pairing code.")

        resolved, err = _resolve_or_fail(params.get("path", ""))
        if err:
            return ToolResult.failure(err)

        max_lines = int(params.get("max_lines") or 500)
        audit_log("paired_fs_read", pairing_code=code, detail={"path": resolved}, success=None)

        raw = await _agent_fs(
            code,
            {"type": "file_read", "path": resolved, "max_lines": max_lines},
        )
        if raw.get("_offline"):
            audit_log("paired_fs_read", pairing_code=code, detail={"offline": True}, success=False)
            return ToolResult.failure(raw.get("error") or "Paired laptop offline")

        if not raw.get("success"):
            audit_log("paired_fs_read", pairing_code=code, detail={"error": raw.get("error")}, success=False)
            return ToolResult.failure(raw.get("error") or "Failed to read file")

        audit_log("paired_fs_read", pairing_code=code, detail={"lines": raw.get("lines")}, success=True)
        return ToolResult.success(
            raw.get("content") or "",
            path=raw.get("path") or resolved,
            lines=raw.get("lines"),
            language=raw.get("language"),
            size=raw.get("size"),
        )


@tool_registry.register
class PairedWriteFileTool(BaseTool):
    """Write a text file on the paired laptop."""

    name: ClassVar[str] = "paired_write_file"
    description: ClassVar[str] = (
        "Write or overwrite a file on the paired remote laptop. "
        "Paths must be inside workspace_root when it is configured."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.MEDIUM
    requires_approval: ClassVar[bool] = True
    timeout: ClassVar[int] = 120

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path on the paired laptop"},
            "content": {"type": "string", "description": "Full file content to write"},
            "create_backup": {"type": "boolean", "description": "Backup existing file as .backup"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, params: dict) -> ToolResult:
        cap_err = _require_capability(Capability.WRITE_FS)
        if cap_err:
            return ToolResult.failure(cap_err)

        code = get_pairing_code()
        if not code:
            return ToolResult.failure("No pairing context: run via Mission/Autonomous with a pairing code.")

        resolved, err = _resolve_or_fail(params.get("path", ""))
        if err:
            return ToolResult.failure(err)

        content = params.get("content")
        if content is None:
            return ToolResult.failure("content is required")

        create_backup = bool(params.get("create_backup", True))
        audit_log("paired_fs_write", pairing_code=code, detail={"path": resolved}, success=None)

        raw = await _agent_fs(
            code,
            {
                "type": "file_write",
                "path": resolved,
                "content": content,
                "create_backup": create_backup,
            },
        )
        if raw.get("_offline"):
            audit_log("paired_fs_write", pairing_code=code, detail={"offline": True}, success=False)
            return ToolResult.failure(raw.get("error") or "Paired laptop offline")

        if not raw.get("success"):
            audit_log("paired_fs_write", pairing_code=code, detail={"error": raw.get("error")}, success=False)
            return ToolResult.failure(raw.get("error") or "Failed to write file")

        audit_log("paired_fs_write", pairing_code=code, detail={"backup": raw.get("backup_path")}, success=True)
        return ToolResult.success(
            raw.get("message") or f"Written to {resolved}",
            path=raw.get("path") or resolved,
            backup_path=raw.get("backup_path"),
            bytes_written=raw.get("bytes_written"),
        )


@tool_registry.register
class PairedListDirectoryTool(BaseTool):
    """List a directory on the paired laptop."""

    name: ClassVar[str] = "paired_list_directory"
    description: ClassVar[str] = (
        "List files and folders on the paired remote laptop. "
        "Use workspace-relative paths when workspace_root is set."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.LOW
    timeout: ClassVar[int] = 120

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path on the paired laptop"},
            "show_hidden": {"type": "boolean"},
        },
        "required": ["path"],
    }

    async def execute(self, params: dict) -> ToolResult:
        cap_err = _require_capability(Capability.READ_FS)
        if cap_err:
            return ToolResult.failure(cap_err)

        code = get_pairing_code()
        if not code:
            return ToolResult.failure("No pairing context: run via Mission/Autonomous with a pairing code.")

        resolved, err = _resolve_or_fail(params.get("path", ""))
        if err:
            return ToolResult.failure(err)

        show_hidden = bool(params.get("show_hidden", False))
        raw = await _agent_fs(
            code,
            {"type": "directory_list", "path": resolved, "show_hidden": show_hidden},
        )
        if raw.get("_offline"):
            return ToolResult.failure(raw.get("error") or "Paired laptop offline")

        if not raw.get("success"):
            return ToolResult.failure(raw.get("error") or "Directory listing failed")

        files = raw.get("files") or []
        return ToolResult.success(
            files,
            path=raw.get("path") or resolved,
            count=raw.get("count", len(files)),
        )


__all__ = [
    "PairedReadFileTool",
    "PairedWriteFileTool",
    "PairedListDirectoryTool",
]
