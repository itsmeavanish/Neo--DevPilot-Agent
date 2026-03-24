"""
VS Code control tool.

Launch VS Code and open files/projects.
"""

import asyncio
import os
import platform
import subprocess
from pathlib import Path
from typing import ClassVar

from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import tool_registry
from jarvis.core.constants import RiskLevel

IS_WINDOWS = platform.system() == "Windows"


@tool_registry.register
class VSCodeTool(BaseTool):
    """Control VS Code editor."""

    name: ClassVar[str] = "vscode"
    description: ClassVar[str] = (
        "Control Visual Studio Code. Open files, folders, or launch VS Code. "
        "Can also open with Cursor IDE if preferred."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.LOW
    timeout: ClassVar[int] = 30

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open", "open_file", "open_folder", "diff", "goto"],
                "description": "Action to perform",
            },
            "path": {
                "type": "string",
                "description": "File or folder path to open",
            },
            "path2": {
                "type": "string",
                "description": "Second path for diff operation",
            },
            "line": {
                "type": "integer",
                "description": "Line number to go to",
                "minimum": 1,
            },
            "column": {
                "type": "integer",
                "description": "Column number to go to",
                "minimum": 1,
            },
            "editor": {
                "type": "string",
                "enum": ["code", "cursor"],
                "description": "Which editor to use (default: code)",
            },
            "new_window": {
                "type": "boolean",
                "description": "Open in new window",
            },
            "wait": {
                "type": "boolean",
                "description": "Wait for editor to close",
            },
        },
        "required": ["action"],
    }

    # Editor executable paths
    EDITORS = {
        "code": ["code", "code.cmd", "code-insiders", "code-insiders.cmd"],
        "cursor": ["cursor", "cursor.cmd"],
    }

    async def execute(self, params: dict) -> ToolResult:
        action = params["action"]
        path = params.get("path")
        path2 = params.get("path2")
        line = params.get("line")
        column = params.get("column")
        editor = params.get("editor", "code")
        new_window = params.get("new_window", False)
        wait = params.get("wait", False)

        # Find editor executable
        editor_cmd = await self._find_editor(editor)
        if not editor_cmd:
            return ToolResult.failure(
                f"Editor '{editor}' not found. Make sure it's installed and in PATH."
            )

        # Build command
        cmd = [editor_cmd]

        if new_window:
            cmd.append("--new-window")
        if wait:
            cmd.append("--wait")

        if action == "open":
            # Just launch VS Code
            pass

        elif action == "open_file":
            if not path:
                return ToolResult.failure("Path is required for open_file action")
            resolved = Path(path).expanduser().resolve()
            if not resolved.exists():
                return ToolResult.failure(f"File not found: {resolved}")

            file_arg = str(resolved)
            if line:
                file_arg += f":{line}"
                if column:
                    file_arg += f":{column}"
            cmd.append(file_arg)

        elif action == "open_folder":
            if not path:
                return ToolResult.failure("Path is required for open_folder action")
            resolved = Path(path).expanduser().resolve()
            if not resolved.exists():
                return ToolResult.failure(f"Folder not found: {resolved}")
            if not resolved.is_dir():
                return ToolResult.failure(f"Not a directory: {resolved}")
            cmd.append(str(resolved))

        elif action == "diff":
            if not path or not path2:
                return ToolResult.failure("Both path and path2 are required for diff action")
            resolved1 = Path(path).expanduser().resolve()
            resolved2 = Path(path2).expanduser().resolve()
            if not resolved1.exists():
                return ToolResult.failure(f"File not found: {resolved1}")
            if not resolved2.exists():
                return ToolResult.failure(f"File not found: {resolved2}")
            cmd.extend(["--diff", str(resolved1), str(resolved2)])

        elif action == "goto":
            if not path:
                return ToolResult.failure("Path is required for goto action")
            if not line:
                return ToolResult.failure("Line is required for goto action")
            resolved = Path(path).expanduser().resolve()
            if not resolved.exists():
                return ToolResult.failure(f"File not found: {resolved}")
            cmd.extend(["--goto", f"{resolved}:{line}"])

        self.logger.info(f"Launching editor: {' '.join(cmd)}")

        try:
            # Don't wait for VS Code (it stays open)
            if wait:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    return ToolResult.failure(result.stderr or "Failed to open editor")
            else:
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )

            return ToolResult.success(
                f"Opened {editor} successfully",
                editor=editor,
                action=action,
                path=path,
            )

        except FileNotFoundError:
            return ToolResult.failure(f"Editor executable not found: {editor_cmd}")
        except Exception as e:
            return ToolResult.failure(f"Failed to launch editor: {e}")

    async def _find_editor(self, editor: str) -> str | None:
        """Find the editor executable."""
        candidates = self.EDITORS.get(editor, [editor])

        for candidate in candidates:
            # Check if it's in PATH
            if IS_WINDOWS:
                # Use where command
                try:
                    result = subprocess.run(
                        ["where", candidate],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        return candidate
                except Exception:
                    pass
            else:
                # Use which command
                try:
                    result = subprocess.run(
                        ["which", candidate],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        return candidate
                except Exception:
                    pass

        # Check common installation paths on Windows
        if IS_WINDOWS and editor == "code":
            common_paths = [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd"),
                os.path.expandvars(r"%ProgramFiles%\Microsoft VS Code\bin\code.cmd"),
            ]
            for p in common_paths:
                if os.path.exists(p):
                    return p

        return None


__all__ = ["VSCodeTool"]
