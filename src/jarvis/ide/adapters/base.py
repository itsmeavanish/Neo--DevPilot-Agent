"""
Base IDE adapter interface.

Defines the interface that all IDE adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Awaitable

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
)


class BaseIDEAdapter(ABC):
    """
    Abstract base class for IDE adapters.

    Each IDE adapter provides integration with a specific IDE.
    """

    name: str = "base"
    ide_type: IDEType = IDEType.UNKNOWN

    def __init__(self):
        self.logger = get_logger(f"jarvis.ide.adapters.{self.name}")
        self.connected = False
        self.workspace: WorkspaceInfo | None = None

        # Callbacks
        self._on_file_change: Callable | None = None
        self._on_diagnostic: Callable | None = None

    # ═══════════════════════════════════════════════════════════════
    # Connection Management
    # ═══════════════════════════════════════════════════════════════

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the IDE.

        Returns:
            True if connected successfully
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the IDE."""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected to the IDE."""
        pass

    # ═══════════════════════════════════════════════════════════════
    # Workspace Operations
    # ═══════════════════════════════════════════════════════════════

    @abstractmethod
    async def get_workspace_info(self) -> WorkspaceInfo | None:
        """Get information about the current workspace."""
        pass

    @abstractmethod
    async def get_open_files(self) -> list[str]:
        """Get list of currently open files."""
        pass

    @abstractmethod
    async def get_active_file(self) -> str | None:
        """Get the currently active file."""
        pass

    # ═══════════════════════════════════════════════════════════════
    # File Operations
    # ═══════════════════════════════════════════════════════════════

    @abstractmethod
    async def open_file(self, path: str, line: int | None = None, column: int | None = None) -> bool:
        """
        Open a file in the IDE.

        Args:
            path: File path
            line: Optional line number to go to
            column: Optional column number

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def close_file(self, path: str) -> bool:
        """Close a file in the IDE."""
        pass

    @abstractmethod
    async def get_file_content(self, path: str) -> str | None:
        """Get content of a file from the IDE."""
        pass

    @abstractmethod
    async def apply_edit(self, edit: FileEdit) -> bool:
        """
        Apply an edit to a file.

        Args:
            edit: The edit to apply

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def save_file(self, path: str) -> bool:
        """Save a file."""
        pass

    @abstractmethod
    async def save_all(self) -> bool:
        """Save all open files."""
        pass

    # ═══════════════════════════════════════════════════════════════
    # Diagnostics
    # ═══════════════════════════════════════════════════════════════

    @abstractmethod
    async def get_diagnostics(self, path: str | None = None) -> list[Diagnostic]:
        """
        Get diagnostics (errors, warnings) from the IDE.

        Args:
            path: Optional file path to filter by

        Returns:
            List of diagnostics
        """
        pass

    @abstractmethod
    async def clear_diagnostics(self, path: str | None = None) -> None:
        """Clear diagnostics."""
        pass

    # ═══════════════════════════════════════════════════════════════
    # Code Intelligence
    # ═══════════════════════════════════════════════════════════════

    @abstractmethod
    async def get_symbols(self, path: str) -> list[Symbol]:
        """Get symbols in a file."""
        pass

    @abstractmethod
    async def find_references(self, path: str, position: Position) -> list[tuple[str, Range]]:
        """Find references to a symbol."""
        pass

    @abstractmethod
    async def go_to_definition(self, path: str, position: Position) -> tuple[str, Position] | None:
        """Go to definition of a symbol."""
        pass

    @abstractmethod
    async def get_completions(self, path: str, position: Position) -> list[CompletionItem]:
        """Get code completions at a position."""
        pass

    # ═══════════════════════════════════════════════════════════════
    # Commands
    # ═══════════════════════════════════════════════════════════════

    @abstractmethod
    async def execute_command(self, command: IDECommand) -> Any:
        """Execute an IDE command."""
        pass

    @abstractmethod
    async def get_available_commands(self) -> list[str]:
        """Get list of available IDE commands."""
        pass

    # ═══════════════════════════════════════════════════════════════
    # Terminal
    # ═══════════════════════════════════════════════════════════════

    @abstractmethod
    async def run_in_terminal(self, command: str, name: str | None = None) -> bool:
        """
        Run a command in the IDE's integrated terminal.

        Args:
            command: Command to run
            name: Optional terminal name

        Returns:
            True if successful
        """
        pass

    # ═══════════════════════════════════════════════════════════════
    # Notifications
    # ═══════════════════════════════════════════════════════════════

    @abstractmethod
    async def show_message(self, message: str, level: str = "info") -> None:
        """Show a message in the IDE."""
        pass

    @abstractmethod
    async def show_input(self, prompt: str, default: str | None = None) -> str | None:
        """Show an input prompt in the IDE."""
        pass

    # ═══════════════════════════════════════════════════════════════
    # Callbacks
    # ═══════════════════════════════════════════════════════════════

    def on_file_change(self, callback: Callable) -> None:
        """Register callback for file changes."""
        self._on_file_change = callback

    def on_diagnostic(self, callback: Callable) -> None:
        """Register callback for new diagnostics."""
        self._on_diagnostic = callback


__all__ = ["BaseIDEAdapter"]
