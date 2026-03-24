"""
Cursor IDE adapter.

Cursor is based on VS Code, so this adapter extends the VS Code adapter.
"""

import os
import shutil

from jarvis.ide.adapters.vscode import VSCodeAdapter
from jarvis.ide.models import IDEType


class CursorAdapter(VSCodeAdapter):
    """
    Cursor IDE adapter.

    Cursor is a fork of VS Code with AI features, so most VS Code
    functionality works the same way.
    """

    name = "cursor"
    ide_type = IDEType.CURSOR

    def _detect_cli(self) -> None:
        """Detect Cursor CLI path."""
        # Try common CLI names for Cursor
        for cli_name in ["cursor", "cursor.cmd"]:
            path = shutil.which(cli_name)
            if path:
                self.cli_path = path
                self.logger.debug(f"Found Cursor CLI: {path}")
                return

        # Check common installation paths on Windows
        if os.name == "nt":
            common_paths = [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\cursor\resources\app\bin\cursor.cmd"),
                os.path.expandvars(r"%LOCALAPPDATA%\cursor\cursor.cmd"),
                os.path.expandvars(r"%PROGRAMFILES%\Cursor\resources\app\bin\cursor.cmd"),
            ]
            for path in common_paths:
                if os.path.exists(path):
                    self.cli_path = path
                    self.logger.debug(f"Found Cursor CLI: {path}")
                    return

        # macOS paths
        mac_paths = [
            "/Applications/Cursor.app/Contents/Resources/app/bin/cursor",
            os.path.expanduser("~/Applications/Cursor.app/Contents/Resources/app/bin/cursor"),
        ]
        for path in mac_paths:
            if os.path.exists(path):
                self.cli_path = path
                self.logger.debug(f"Found Cursor CLI: {path}")
                return

        # Fall back to VS Code CLI if Cursor not found
        self.logger.warning("Cursor CLI not found, falling back to VS Code")
        super()._detect_cli()


__all__ = ["CursorAdapter"]
