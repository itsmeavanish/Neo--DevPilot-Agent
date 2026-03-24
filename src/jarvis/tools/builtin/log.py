"""
Log reader tool.

Read and search log files.
"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import tool_registry
from jarvis.core.constants import RiskLevel


@tool_registry.register
class LogReaderTool(BaseTool):
    """Read and search log files."""

    name: ClassVar[str] = "read_logs"
    description: ClassVar[str] = (
        "Read and search log files. Can tail logs, search for patterns, "
        "and filter by log level. Useful for debugging and monitoring."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.LOW
    timeout: ClassVar[int] = 30

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to log file",
            },
            "action": {
                "type": "string",
                "enum": ["read", "tail", "search", "errors"],
                "description": "Action to perform (default: read)",
            },
            "lines": {
                "type": "integer",
                "description": "Number of lines to read/tail",
                "minimum": 1,
                "maximum": 1000,
            },
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for",
            },
            "level": {
                "type": "string",
                "enum": ["debug", "info", "warn", "warning", "error", "critical", "fatal"],
                "description": "Filter by log level",
            },
            "since": {
                "type": "string",
                "description": "Show logs since time (ISO format or relative like '1h', '30m')",
            },
            "context": {
                "type": "integer",
                "description": "Lines of context around matches",
                "minimum": 0,
                "maximum": 10,
            },
        },
        "required": ["path"],
    }

    # Common log level patterns
    LOG_LEVEL_PATTERNS = {
        "debug": r"\b(DEBUG|DBG)\b",
        "info": r"\b(INFO|INF)\b",
        "warn": r"\b(WARN|WARNING|WRN)\b",
        "warning": r"\b(WARN|WARNING|WRN)\b",
        "error": r"\b(ERROR|ERR)\b",
        "critical": r"\b(CRITICAL|CRIT|FATAL)\b",
        "fatal": r"\b(CRITICAL|CRIT|FATAL)\b",
    }

    # Max file size to read (50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024

    async def execute(self, params: dict) -> ToolResult:
        path_str = params["path"]
        action = params.get("action", "read")
        lines = params.get("lines", 100)
        pattern = params.get("pattern")
        level = params.get("level")
        since = params.get("since")
        context = params.get("context", 0)

        # Resolve path
        path = Path(path_str).expanduser().resolve()

        if not path.exists():
            return ToolResult.failure(f"Log file not found: {path}")

        if not path.is_file():
            return ToolResult.failure(f"Not a file: {path}")

        # Check file size
        size = path.stat().st_size
        if size > self.MAX_FILE_SIZE:
            return ToolResult.failure(
                f"File too large: {size / 1024 / 1024:.1f}MB (max: {self.MAX_FILE_SIZE / 1024 / 1024}MB). "
                "Use 'tail' action instead."
            )

        try:
            if action == "read":
                return await self._read_logs(path, lines)

            elif action == "tail":
                return await self._tail_logs(path, lines)

            elif action == "search":
                if not pattern:
                    return ToolResult.failure("Pattern is required for search action")
                return await self._search_logs(path, pattern, lines, context)

            elif action == "errors":
                return await self._find_errors(path, lines, level)

            else:
                return ToolResult.failure(f"Unknown action: {action}")

        except Exception as e:
            return ToolResult.failure(f"Failed to read logs: {e}")

    async def _read_logs(self, path: Path, lines: int) -> ToolResult:
        """Read first N lines of log file."""
        try:
            content = path.read_text(errors='replace')
            log_lines = content.splitlines()[:lines]

            return ToolResult.success(
                "\n".join(log_lines),
                path=str(path),
                lines_returned=len(log_lines),
                total_lines=len(content.splitlines()),
            )
        except Exception as e:
            return ToolResult.failure(f"Error reading file: {e}")

    async def _tail_logs(self, path: Path, lines: int) -> ToolResult:
        """Read last N lines of log file."""
        try:
            # Efficient tail using seek
            with open(path, 'rb') as f:
                # Go to end
                f.seek(0, 2)
                file_size = f.tell()

                # Read chunks from end
                chunk_size = 8192
                found_lines = []
                position = file_size

                while len(found_lines) < lines + 1 and position > 0:
                    read_size = min(chunk_size, position)
                    position -= read_size
                    f.seek(position)
                    chunk = f.read(read_size).decode('utf-8', errors='replace')
                    found_lines = chunk.splitlines() + found_lines

            # Take last N lines
            result_lines = found_lines[-lines:]

            return ToolResult.success(
                "\n".join(result_lines),
                path=str(path),
                lines_returned=len(result_lines),
            )
        except Exception as e:
            return ToolResult.failure(f"Error tailing file: {e}")

    async def _search_logs(
        self, path: Path, pattern: str, max_matches: int, context: int
    ) -> ToolResult:
        """Search logs for pattern."""
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return ToolResult.failure(f"Invalid regex pattern: {e}")

        try:
            content = path.read_text(errors='replace')
            lines = content.splitlines()
            matches = []

            for i, line in enumerate(lines):
                if regex.search(line):
                    match_info = {
                        'line_number': i + 1,
                        'content': line,
                    }

                    # Add context if requested
                    if context > 0:
                        start = max(0, i - context)
                        end = min(len(lines), i + context + 1)
                        match_info['context'] = {
                            'before': lines[start:i],
                            'after': lines[i + 1:end],
                        }

                    matches.append(match_info)

                    if len(matches) >= max_matches:
                        break

            return ToolResult.success(
                matches,
                path=str(path),
                pattern=pattern,
                matches_found=len(matches),
                truncated=len(matches) >= max_matches,
            )
        except Exception as e:
            return ToolResult.failure(f"Error searching file: {e}")

    async def _find_errors(self, path: Path, max_lines: int, level: str | None) -> ToolResult:
        """Find error/warning lines in logs."""
        # Build pattern for log levels
        if level:
            patterns = [self.LOG_LEVEL_PATTERNS.get(level.lower(), r"\bERROR\b")]
        else:
            # Default: errors and above
            patterns = [
                self.LOG_LEVEL_PATTERNS["error"],
                self.LOG_LEVEL_PATTERNS["critical"],
            ]

        combined_pattern = "|".join(patterns)

        try:
            regex = re.compile(combined_pattern, re.IGNORECASE)
            content = path.read_text(errors='replace')
            lines = content.splitlines()

            errors = []
            for i, line in enumerate(lines):
                if regex.search(line):
                    errors.append({
                        'line_number': i + 1,
                        'content': line,
                    })

                    if len(errors) >= max_lines:
                        break

            return ToolResult.success(
                errors,
                path=str(path),
                level_filter=level or "error+",
                errors_found=len(errors),
            )
        except Exception as e:
            return ToolResult.failure(f"Error finding errors: {e}")


__all__ = ["LogReaderTool"]
