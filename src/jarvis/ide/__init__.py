"""
IDE integration for JARVIS.

Provides integration with various IDEs including VS Code, Cursor, and others.
"""

from jarvis.ide.models import (
    IDEType,
    DiagnosticSeverity,
    FileChangeType,
    Position,
    Range,
    Diagnostic,
    FileChange,
    TextEdit,
    FileEdit,
    WorkspaceInfo,
    Symbol,
    CompletionItem,
    IDECommand,
)
from jarvis.ide.adapters.base import BaseIDEAdapter
from jarvis.ide.adapters.vscode import VSCodeAdapter
from jarvis.ide.adapters.cursor import CursorAdapter
from jarvis.ide.manager import IDEManager, get_ide_manager

__all__ = [
    # Models
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
    # Adapters
    "BaseIDEAdapter",
    "VSCodeAdapter",
    "CursorAdapter",
    # Manager
    "IDEManager",
    "get_ide_manager",
]
