"""
IDE Manager.

Manages IDE adapters, auto-detection, and provides unified interface.
"""

import os
import shutil
from typing import Any

from jarvis.core.logging import get_logger
from jarvis.ide.models import (
    IDEType,
    WorkspaceInfo,
    Diagnostic,
    FileEdit,
    Symbol,
    CompletionItem,
    IDECommand,
    Position,
    Range,
    TextEdit,
)
from jarvis.ide.adapters.base import BaseIDEAdapter
from jarvis.ide.adapters.vscode import VSCodeAdapter
from jarvis.ide.adapters.cursor import CursorAdapter

logger = get_logger("jarvis.ide.manager")


class IDEManager:
    """
    Manages IDE integrations.

    Features:
    - Auto-detection of installed IDEs
    - Unified interface across different IDEs
    - Adapter registration
    - Diagnostics aggregation
    """

    def __init__(self):
        self.logger = get_logger("jarvis.ide.manager")
        self.adapters: dict[IDEType, BaseIDEAdapter] = {}
        self.active_adapter: BaseIDEAdapter | None = None

        # Initialize with detected adapters
        self._init_adapters()

    def _init_adapters(self) -> None:
        """Initialize and detect available adapters."""
        # VS Code
        vscode = VSCodeAdapter()
        if vscode.cli_path:
            self.adapters[IDEType.VSCODE] = vscode
            self.logger.info("VS Code adapter available")

        # Cursor
        cursor = CursorAdapter()
        if cursor.cli_path:
            self.adapters[IDEType.CURSOR] = cursor
            self.logger.info("Cursor adapter available")

        # Set default active adapter (prefer Cursor, then VS Code)
        if IDEType.CURSOR in self.adapters:
            self.active_adapter = self.adapters[IDEType.CURSOR]
        elif IDEType.VSCODE in self.adapters:
            self.active_adapter = self.adapters[IDEType.VSCODE]

    def get_adapter(self, ide_type: IDEType | None = None) -> BaseIDEAdapter | None:
        """
        Get an IDE adapter.

        Args:
            ide_type: Specific IDE type, or None for active adapter

        Returns:
            IDE adapter or None
        """
        if ide_type:
            return self.adapters.get(ide_type)
        return self.active_adapter

    def set_active(self, ide_type: IDEType) -> bool:
        """
        Set the active IDE adapter.

        Args:
            ide_type: IDE type to activate

        Returns:
            True if successful
        """
        if ide_type in self.adapters:
            self.active_adapter = self.adapters[ide_type]
            return True
        return False

    def list_available(self) -> list[IDEType]:
        """Get list of available IDE types."""
        return list(self.adapters.keys())

    async def connect(self, ide_type: IDEType | None = None) -> bool:
        """Connect to an IDE."""
        adapter = self.get_adapter(ide_type)
        if adapter:
            return await adapter.connect()
        return False

    # ═══════════════════════════════════════════════════════════════
    # Convenience Methods (delegate to active adapter)
    # ═══════════════════════════════════════════════════════════════

    async def open_file(
        self,
        path: str,
        line: int | None = None,
        column: int | None = None,
    ) -> bool:
        """Open a file in the active IDE."""
        if not self.active_adapter:
            return False
        return await self.active_adapter.open_file(path, line, column)

    async def get_diagnostics(self, path: str | None = None) -> list[Diagnostic]:
        """Get diagnostics from the active IDE."""
        if not self.active_adapter:
            return []
        return await self.active_adapter.get_diagnostics(path)

    async def apply_edit(self, edit: FileEdit) -> bool:
        """Apply an edit in the active IDE."""
        if not self.active_adapter:
            return False
        return await self.active_adapter.apply_edit(edit)

    async def run_in_terminal(self, command: str, name: str | None = None) -> bool:
        """Run a command in the IDE terminal."""
        if not self.active_adapter:
            return False
        return await self.active_adapter.run_in_terminal(command, name)

    async def execute_command(self, command: str, args: list[Any] | None = None) -> Any:
        """Execute an IDE command."""
        if not self.active_adapter:
            return None
        return await self.active_adapter.execute_command(
            IDECommand(command=command, args=args or [])
        )

    async def show_message(self, message: str, level: str = "info") -> None:
        """Show a message in the IDE."""
        if self.active_adapter:
            await self.active_adapter.show_message(message, level)

    async def get_workspace_info(self) -> WorkspaceInfo | None:
        """Get workspace information."""
        if not self.active_adapter:
            return None
        return await self.active_adapter.get_workspace_info()

    # ═══════════════════════════════════════════════════════════════
    # High-Level Operations
    # ═══════════════════════════════════════════════════════════════

    async def goto_error(self, diagnostic: Diagnostic) -> bool:
        """Navigate to a diagnostic location."""
        if not self.active_adapter:
            return False

        if diagnostic.range:
            return await self.active_adapter.open_file(
                diagnostic.file_path,
                diagnostic.range.start.line + 1,
                diagnostic.range.start.character + 1,
            )
        return await self.active_adapter.open_file(diagnostic.file_path)

    async def insert_text(
        self,
        path: str,
        line: int,
        column: int,
        text: str,
    ) -> bool:
        """Insert text at a position."""
        edit = FileEdit(
            file_path=path,
            edits=[
                TextEdit(
                    range=Range(
                        Position(line, column),
                        Position(line, column),
                    ),
                    new_text=text,
                )
            ],
        )
        return await self.apply_edit(edit)

    async def replace_text(
        self,
        path: str,
        start_line: int,
        start_col: int,
        end_line: int,
        end_col: int,
        new_text: str,
    ) -> bool:
        """Replace text in a range."""
        edit = FileEdit(
            file_path=path,
            edits=[
                TextEdit(
                    range=Range(
                        Position(start_line, start_col),
                        Position(end_line, end_col),
                    ),
                    new_text=new_text,
                )
            ],
        )
        return await self.apply_edit(edit)

    async def get_all_errors(self) -> list[Diagnostic]:
        """Get all error-level diagnostics."""
        diagnostics = await self.get_diagnostics()
        return [d for d in diagnostics if d.severity.value == "error"]

    async def get_all_warnings(self) -> list[Diagnostic]:
        """Get all warning-level diagnostics."""
        diagnostics = await self.get_diagnostics()
        return [d for d in diagnostics if d.severity.value == "warning"]

    async def fix_diagnostic(self, diagnostic: Diagnostic, fix: str) -> bool:
        """
        Apply a fix to a diagnostic.

        Args:
            diagnostic: The diagnostic to fix
            fix: The replacement text

        Returns:
            True if successful
        """
        if not diagnostic.range:
            return False

        return await self.replace_text(
            diagnostic.file_path,
            diagnostic.range.start.line,
            diagnostic.range.start.character,
            diagnostic.range.end.line,
            diagnostic.range.end.character,
            fix,
        )


# ═══════════════════════════════════════════════════════════════
# Module-level singleton
# ═══════════════════════════════════════════════════════════════

_manager: IDEManager | None = None


def get_ide_manager() -> IDEManager:
    """Get singleton IDE manager."""
    global _manager
    if _manager is None:
        _manager = IDEManager()
    return _manager


__all__ = ["IDEManager", "get_ide_manager"]
