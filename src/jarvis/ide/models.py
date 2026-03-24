"""
IDE integration models.

Defines models for IDE adapters, diagnostics, and file operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class IDEType(Enum):
    """Supported IDE types."""
    VSCODE = "vscode"
    CURSOR = "cursor"
    NEOVIM = "neovim"
    JETBRAINS = "jetbrains"
    SUBLIME = "sublime"
    UNKNOWN = "unknown"


class DiagnosticSeverity(Enum):
    """Diagnostic severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


class FileChangeType(Enum):
    """Types of file changes."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class Position:
    """Position in a file (0-indexed)."""
    line: int
    character: int

    def to_dict(self) -> dict[str, int]:
        return {"line": self.line, "character": self.character}

    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        return cls(line=data.get("line", 0), character=data.get("character", 0))


@dataclass
class Range:
    """Range in a file."""
    start: Position
    end: Position

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start.to_dict(), "end": self.end.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> "Range":
        return cls(
            start=Position.from_dict(data.get("start", {})),
            end=Position.from_dict(data.get("end", {})),
        )


@dataclass
class Diagnostic:
    """A diagnostic message (error, warning, etc.)."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    file_path: str = ""
    range: Range | None = None
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR
    message: str = ""
    source: str = ""               # e.g., "typescript", "eslint", "python"
    code: str | None = None        # Error code
    related_info: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if isinstance(self.severity, str):
            self.severity = DiagnosticSeverity(self.severity)

    @property
    def location_string(self) -> str:
        """Get human-readable location string."""
        if self.range:
            return f"{self.file_path}:{self.range.start.line + 1}:{self.range.start.character + 1}"
        return self.file_path

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "range": self.range.to_dict() if self.range else None,
            "severity": self.severity.value,
            "message": self.message,
            "source": self.source,
            "code": self.code,
            "related_info": self.related_info,
            "location": self.location_string,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Diagnostic":
        range_data = data.get("range")
        return cls(
            id=data.get("id", str(uuid4())[:8]),
            file_path=data.get("file_path", ""),
            range=Range.from_dict(range_data) if range_data else None,
            severity=DiagnosticSeverity(data.get("severity", "error")),
            message=data.get("message", ""),
            source=data.get("source", ""),
            code=data.get("code"),
            related_info=data.get("related_info", []),
        )


@dataclass
class FileChange:
    """A file change event."""
    type: FileChangeType
    path: str
    old_path: str | None = None    # For renames
    content: str | None = None     # For content changes
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = FileChangeType(self.type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "path": self.path,
            "old_path": self.old_path,
            "has_content": self.content is not None,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TextEdit:
    """A text edit operation."""
    range: Range
    new_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "range": self.range.to_dict(),
            "new_text": self.new_text,
        }


@dataclass
class FileEdit:
    """Edits to a file."""
    file_path: str
    edits: list[TextEdit] = field(default_factory=list)
    create_if_missing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "edits": [e.to_dict() for e in self.edits],
            "create_if_missing": self.create_if_missing,
        }


@dataclass
class WorkspaceInfo:
    """Information about the IDE workspace."""
    root_path: str
    name: str = ""
    folders: list[str] = field(default_factory=list)
    open_files: list[str] = field(default_factory=list)
    active_file: str | None = None
    ide_type: IDEType = IDEType.UNKNOWN
    ide_version: str | None = None

    def __post_init__(self):
        if isinstance(self.ide_type, str):
            self.ide_type = IDEType(self.ide_type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_path": self.root_path,
            "name": self.name,
            "folders": self.folders,
            "open_files": self.open_files,
            "active_file": self.active_file,
            "ide_type": self.ide_type.value,
            "ide_version": self.ide_version,
        }


@dataclass
class Symbol:
    """A code symbol (function, class, variable, etc.)."""
    name: str
    kind: str                      # function, class, variable, etc.
    file_path: str
    range: Range | None = None
    container: str | None = None   # Parent symbol name
    detail: str | None = None      # Additional info

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "file_path": self.file_path,
            "range": self.range.to_dict() if self.range else None,
            "container": self.container,
            "detail": self.detail,
        }


@dataclass
class CompletionItem:
    """A code completion suggestion."""
    label: str
    kind: str                      # function, variable, class, etc.
    detail: str | None = None
    documentation: str | None = None
    insert_text: str | None = None
    sort_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "kind": self.kind,
            "detail": self.detail,
            "documentation": self.documentation,
            "insert_text": self.insert_text or self.label,
        }


@dataclass
class IDECommand:
    """A command to execute in the IDE."""
    command: str
    args: list[Any] = field(default_factory=list)
    title: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "args": self.args,
            "title": self.title,
        }


__all__ = [
    "IDEType",
    "DiagnosticSeverity",
    "FileChangeType",
    "Position",
    "Range",
    "Diagnostic",
    "FileChange",
    "TextEdit",
    "FileEdit",
    "WorkspaceInfo",
    "Symbol",
    "CompletionItem",
    "IDECommand",
]
