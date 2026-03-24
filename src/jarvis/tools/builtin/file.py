"""
File operation tools.

Read, write, and list files/directories.
"""

import os
from pathlib import Path
from typing import ClassVar

from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import tool_registry
from jarvis.core.constants import RiskLevel


@tool_registry.register
class ReadFileTool(BaseTool):
    """Read contents of a file."""

    name: ClassVar[str] = "read_file"
    description: ClassVar[str] = (
        "Read the contents of a file. Returns the file content as text. "
        "Useful for examining source code, configuration files, logs, etc."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.LOW
    timeout: ClassVar[int] = 10

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file (absolute or relative)",
            },
            "encoding": {
                "type": "string",
                "description": "File encoding (default: utf-8)",
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximum number of lines to read",
                "minimum": 1,
            },
            "start_line": {
                "type": "integer",
                "description": "Line number to start reading from (1-indexed)",
                "minimum": 1,
            },
        },
        "required": ["path"],
    }

    # File size limit (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    async def execute(self, params: dict) -> ToolResult:
        path_str = params["path"]
        encoding = params.get("encoding", "utf-8")
        max_lines = params.get("max_lines")
        start_line = params.get("start_line", 1)

        # Resolve path
        path = Path(path_str).expanduser().resolve()

        # Validate path
        if not path.exists():
            return ToolResult.failure(f"File not found: {path}")

        if not path.is_file():
            return ToolResult.failure(f"Not a file: {path}")

        # Check file size
        size = path.stat().st_size
        if size > self.MAX_FILE_SIZE:
            return ToolResult.failure(
                f"File too large: {size / 1024 / 1024:.1f}MB (max: {self.MAX_FILE_SIZE / 1024 / 1024}MB)"
            )

        try:
            content = path.read_text(encoding=encoding)
            lines = content.splitlines()
            total_lines = len(lines)

            # Apply line filtering
            if start_line > 1:
                lines = lines[start_line - 1:]

            if max_lines:
                lines = lines[:max_lines]

            content = "\n".join(lines)

            return ToolResult.success(
                content,
                path=str(path),
                size=size,
                total_lines=total_lines,
                lines_returned=len(lines),
            )

        except UnicodeDecodeError:
            return ToolResult.failure(f"Cannot decode file with encoding '{encoding}'")
        except PermissionError:
            return ToolResult.failure(f"Permission denied: {path}")
        except Exception as e:
            return ToolResult.failure(f"Error reading file: {e}")


@tool_registry.register
class WriteFileTool(BaseTool):
    """Write content to a file."""

    name: ClassVar[str] = "write_file"
    description: ClassVar[str] = (
        "Write or append content to a file. Creates the file if it doesn't exist. "
        "Use mode='append' to add to existing content."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.MEDIUM
    requires_approval: ClassVar[bool] = True
    timeout: ClassVar[int] = 10

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file",
            },
            "content": {
                "type": "string",
                "description": "Content to write",
            },
            "mode": {
                "type": "string",
                "enum": ["overwrite", "append", "create_only"],
                "description": "Write mode: overwrite, append, or create_only",
            },
            "encoding": {
                "type": "string",
                "description": "File encoding (default: utf-8)",
            },
            "create_dirs": {
                "type": "boolean",
                "description": "Create parent directories if they don't exist",
            },
        },
        "required": ["path", "content"],
    }

    async def execute(self, params: dict) -> ToolResult:
        path_str = params["path"]
        content = params["content"]
        mode = params.get("mode", "overwrite")
        encoding = params.get("encoding", "utf-8")
        create_dirs = params.get("create_dirs", False)

        # Resolve path
        path = Path(path_str).expanduser().resolve()

        # Validate
        if mode == "create_only" and path.exists():
            return ToolResult.failure(f"File already exists: {path}")

        # Create parent directories
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        elif not path.parent.exists():
            return ToolResult.failure(f"Parent directory does not exist: {path.parent}")

        try:
            write_mode = "a" if mode == "append" else "w"
            with open(path, write_mode, encoding=encoding) as f:
                f.write(content)

            size = path.stat().st_size
            lines = len(content.splitlines())

            return ToolResult.success(
                f"Written {len(content)} bytes ({lines} lines) to {path}",
                path=str(path),
                bytes_written=len(content),
                lines=lines,
                total_size=size,
            )

        except PermissionError:
            return ToolResult.failure(f"Permission denied: {path}")
        except Exception as e:
            return ToolResult.failure(f"Error writing file: {e}")


@tool_registry.register
class ListDirectoryTool(BaseTool):
    """List contents of a directory."""

    name: ClassVar[str] = "list_directory"
    description: ClassVar[str] = (
        "List files and directories in a path. Returns names, sizes, and types. "
        "Useful for exploring project structure."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.LOW
    timeout: ClassVar[int] = 10

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path to list",
            },
            "recursive": {
                "type": "boolean",
                "description": "List recursively (default: false)",
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum depth for recursive listing",
                "minimum": 1,
                "maximum": 10,
            },
            "include_hidden": {
                "type": "boolean",
                "description": "Include hidden files (starting with .)",
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern to filter files (e.g., '*.py')",
            },
        },
        "required": ["path"],
    }

    MAX_ENTRIES = 1000

    async def execute(self, params: dict) -> ToolResult:
        path_str = params["path"]
        recursive = params.get("recursive", False)
        max_depth = params.get("max_depth", 3)
        include_hidden = params.get("include_hidden", False)
        pattern = params.get("pattern")

        # Resolve path
        path = Path(path_str).expanduser().resolve()

        if not path.exists():
            return ToolResult.failure(f"Path not found: {path}")

        if not path.is_dir():
            return ToolResult.failure(f"Not a directory: {path}")

        try:
            entries = []
            count = 0

            if recursive:
                iterator = path.rglob(pattern or "*") if pattern else path.rglob("*")
            else:
                iterator = path.glob(pattern or "*") if pattern else path.iterdir()

            for entry in iterator:
                if count >= self.MAX_ENTRIES:
                    break

                # Skip hidden files unless requested
                if not include_hidden and entry.name.startswith("."):
                    continue

                # Check depth for recursive
                if recursive:
                    depth = len(entry.relative_to(path).parts)
                    if depth > max_depth:
                        continue

                try:
                    stat = entry.stat()
                    entries.append({
                        "name": str(entry.relative_to(path)),
                        "type": "dir" if entry.is_dir() else "file",
                        "size": stat.st_size if entry.is_file() else None,
                    })
                    count += 1
                except (PermissionError, OSError):
                    continue

            # Sort: directories first, then by name
            entries.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))

            return ToolResult.success(
                entries,
                path=str(path),
                total_entries=len(entries),
                truncated=count >= self.MAX_ENTRIES,
            )

        except PermissionError:
            return ToolResult.failure(f"Permission denied: {path}")
        except Exception as e:
            return ToolResult.failure(f"Error listing directory: {e}")


__all__ = ["ReadFileTool", "WriteFileTool", "ListDirectoryTool"]
