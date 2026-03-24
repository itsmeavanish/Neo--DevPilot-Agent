"""
VS Code IDE adapter.

Provides integration with Visual Studio Code via CLI and extension API.
"""

import asyncio
import json
import subprocess
import os
from pathlib import Path
from typing import Any

from jarvis.core.logging import get_logger
from jarvis.ide.adapters.base import BaseIDEAdapter
from jarvis.ide.models import (
    IDEType,
    WorkspaceInfo,
    Diagnostic,
    DiagnosticSeverity,
    FileEdit,
    TextEdit,
    Symbol,
    CompletionItem,
    IDECommand,
    Position,
    Range,
)


class VSCodeAdapter(BaseIDEAdapter):
    """
    VS Code adapter using CLI and extension integration.

    Supports:
    - Opening files and navigating to positions
    - Reading diagnostics from Problems panel
    - Running commands via the CLI
    - Terminal integration
    """

    name = "vscode"
    ide_type = IDEType.VSCODE

    # Common VS Code commands
    COMMANDS = {
        "save": "workbench.action.files.save",
        "save_all": "workbench.action.files.saveAll",
        "close": "workbench.action.closeActiveEditor",
        "close_all": "workbench.action.closeAllEditors",
        "format": "editor.action.formatDocument",
        "rename": "editor.action.rename",
        "find": "actions.find",
        "replace": "editor.action.startFindReplaceAction",
        "go_to_definition": "editor.action.revealDefinition",
        "find_references": "editor.action.goToReferences",
        "quick_fix": "editor.action.quickFix",
        "toggle_terminal": "workbench.action.terminal.toggleTerminal",
        "new_terminal": "workbench.action.terminal.new",
        "run_task": "workbench.action.tasks.runTask",
        "git_commit": "git.commit",
        "git_push": "git.push",
        "git_pull": "git.pull",
    }

    def __init__(self):
        super().__init__()
        self.cli_path: str | None = None
        self.workspace_path: str | None = None
        self._detect_cli()

    def _detect_cli(self) -> None:
        """Detect VS Code CLI path."""
        import shutil

        # Try common CLI names
        for cli_name in ["code", "code-insiders", "codium"]:
            path = shutil.which(cli_name)
            if path:
                self.cli_path = path
                self.logger.debug(f"Found VS Code CLI: {path}")
                return

        # Check common installation paths on Windows
        if os.name == "nt":
            common_paths = [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd"),
                os.path.expandvars(r"%PROGRAMFILES%\Microsoft VS Code\bin\code.cmd"),
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code Insiders\bin\code-insiders.cmd"),
            ]
            for path in common_paths:
                if os.path.exists(path):
                    self.cli_path = path
                    self.logger.debug(f"Found VS Code CLI: {path}")
                    return

        self.logger.warning("VS Code CLI not found")

    async def connect(self) -> bool:
        """Connect to VS Code."""
        if not self.cli_path:
            self._detect_cli()

        self.connected = self.cli_path is not None

        if self.connected:
            # Try to get workspace info
            self.workspace = await self.get_workspace_info()

        return self.connected

    async def disconnect(self) -> None:
        """Disconnect from VS Code."""
        self.connected = False
        self.workspace = None

    async def is_connected(self) -> bool:
        """Check if connected."""
        return self.connected and self.cli_path is not None

    # ═══════════════════════════════════════════════════════════════
    # Workspace Operations
    # ═══════════════════════════════════════════════════════════════

    async def get_workspace_info(self) -> WorkspaceInfo | None:
        """Get workspace information."""
        if not self.workspace_path:
            self.workspace_path = os.getcwd()

        return WorkspaceInfo(
            root_path=self.workspace_path,
            name=Path(self.workspace_path).name,
            folders=[self.workspace_path],
            ide_type=IDEType.VSCODE,
        )

    async def get_open_files(self) -> list[str]:
        """Get open files (limited without extension)."""
        # Without extension, we can't get this info directly
        return []

    async def get_active_file(self) -> str | None:
        """Get active file (limited without extension)."""
        return None

    # ═══════════════════════════════════════════════════════════════
    # File Operations
    # ═══════════════════════════════════════════════════════════════

    async def open_file(
        self,
        path: str,
        line: int | None = None,
        column: int | None = None,
    ) -> bool:
        """Open a file in VS Code."""
        if not self.cli_path:
            return False

        args = [self.cli_path]

        if line is not None:
            # VS Code uses --goto for line:column
            location = f"{path}:{line}"
            if column is not None:
                location += f":{column}"
            args.extend(["--goto", location])
        else:
            args.append(path)

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                args,
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Failed to open file: {e}")
            return False

    async def close_file(self, path: str) -> bool:
        """Close a file (requires extension)."""
        # Without extension, we can focus on the file and use keyboard shortcut
        # For now, just log warning
        self.logger.warning("close_file requires VS Code extension")
        return False

    async def get_file_content(self, path: str) -> str | None:
        """Get file content (read from disk)."""
        try:
            return Path(path).read_text(encoding="utf-8")
        except Exception as e:
            self.logger.error(f"Failed to read file: {e}")
            return None

    async def apply_edit(self, edit: FileEdit) -> bool:
        """Apply edits to a file."""
        try:
            path = Path(edit.file_path)

            if not path.exists() and edit.create_if_missing:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")

            if not path.exists():
                return False

            # Read current content
            content = path.read_text(encoding="utf-8")
            lines = content.splitlines(keepends=True)

            # Apply edits in reverse order (to preserve line numbers)
            for text_edit in reversed(edit.edits):
                start = text_edit.range.start
                end = text_edit.range.end

                # Build new content
                before = "".join(lines[:start.line])
                if start.line < len(lines):
                    before += lines[start.line][:start.character]

                after = ""
                if end.line < len(lines):
                    after = lines[end.line][end.character:]
                after += "".join(lines[end.line + 1:])

                content = before + text_edit.new_text + after
                lines = content.splitlines(keepends=True)

            # Write back
            path.write_text(content, encoding="utf-8")

            # Open in VS Code to show changes
            await self.open_file(edit.file_path)

            return True

        except Exception as e:
            self.logger.error(f"Failed to apply edit: {e}")
            return False

    async def save_file(self, path: str) -> bool:
        """Save file (send save command)."""
        # Open the file first, then it will auto-save or we can try via extension
        await self.open_file(path)
        return True

    async def save_all(self) -> bool:
        """Save all files."""
        return await self._run_cli_command("--command", "workbench.action.files.saveAll")

    # ═══════════════════════════════════════════════════════════════
    # Diagnostics
    # ═══════════════════════════════════════════════════════════════

    async def get_diagnostics(self, path: str | None = None) -> list[Diagnostic]:
        """
        Get diagnostics from the workspace.

        Note: Without extension, we can try to parse compiler output or use
        language server output if available.
        """
        diagnostics = []

        # Try TypeScript compiler for TS/JS projects
        ts_diagnostics = await self._get_typescript_diagnostics(path)
        diagnostics.extend(ts_diagnostics)

        # Try Python linters
        py_diagnostics = await self._get_python_diagnostics(path)
        diagnostics.extend(py_diagnostics)

        return diagnostics

    async def _get_typescript_diagnostics(self, path: str | None) -> list[Diagnostic]:
        """Get TypeScript/JavaScript diagnostics."""
        diagnostics = []

        # Check if tsconfig exists
        workspace = self.workspace_path or os.getcwd()
        tsconfig = Path(workspace) / "tsconfig.json"
        if not tsconfig.exists():
            return []

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["npx", "tsc", "--noEmit", "--pretty", "false"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Parse TypeScript errors
            # Format: file(line,col): error TS1234: message
            import re
            pattern = r"(.+?)\((\d+),(\d+)\):\s*(error|warning)\s*(TS\d+):\s*(.+)"

            for line in result.stdout.splitlines():
                match = re.match(pattern, line)
                if match:
                    file_path, line_num, col, severity, code, message = match.groups()

                    if path and not file_path.endswith(path):
                        continue

                    diagnostics.append(Diagnostic(
                        file_path=file_path,
                        range=Range(
                            start=Position(int(line_num) - 1, int(col) - 1),
                            end=Position(int(line_num) - 1, int(col)),
                        ),
                        severity=DiagnosticSeverity.ERROR if severity == "error" else DiagnosticSeverity.WARNING,
                        message=message,
                        source="typescript",
                        code=code,
                    ))

        except Exception as e:
            self.logger.debug(f"TypeScript diagnostics failed: {e}")

        return diagnostics

    async def _get_python_diagnostics(self, path: str | None) -> list[Diagnostic]:
        """Get Python diagnostics using ruff or pylint."""
        diagnostics = []

        target = path or "."

        try:
            # Try ruff first (faster)
            result = await asyncio.to_thread(
                subprocess.run,
                ["ruff", "check", "--output-format", "json", target],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.stdout:
                data = json.loads(result.stdout)
                for item in data:
                    diagnostics.append(Diagnostic(
                        file_path=item.get("filename", ""),
                        range=Range(
                            start=Position(
                                item.get("location", {}).get("row", 1) - 1,
                                item.get("location", {}).get("column", 1) - 1,
                            ),
                            end=Position(
                                item.get("end_location", {}).get("row", 1) - 1,
                                item.get("end_location", {}).get("column", 1) - 1,
                            ),
                        ),
                        severity=DiagnosticSeverity.WARNING,
                        message=item.get("message", ""),
                        source="ruff",
                        code=item.get("code"),
                    ))

        except FileNotFoundError:
            pass  # ruff not installed
        except Exception as e:
            self.logger.debug(f"Ruff diagnostics failed: {e}")

        return diagnostics

    async def clear_diagnostics(self, path: str | None = None) -> None:
        """Clear diagnostics (no-op without extension)."""
        pass

    # ═══════════════════════════════════════════════════════════════
    # Code Intelligence
    # ═══════════════════════════════════════════════════════════════

    async def get_symbols(self, path: str) -> list[Symbol]:
        """Get symbols in a file."""
        symbols = []

        # Use ctags if available for basic symbol extraction
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["ctags", "-x", "--output-format=json", path],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    try:
                        data = json.loads(line)
                        symbols.append(Symbol(
                            name=data.get("name", ""),
                            kind=data.get("kind", "unknown"),
                            file_path=path,
                            range=Range(
                                Position(data.get("line", 1) - 1, 0),
                                Position(data.get("line", 1) - 1, 0),
                            ) if data.get("line") else None,
                        ))
                    except json.JSONDecodeError:
                        pass

        except FileNotFoundError:
            pass  # ctags not installed
        except Exception as e:
            self.logger.debug(f"Symbol extraction failed: {e}")

        return symbols

    async def find_references(self, path: str, position: Position) -> list[tuple[str, Range]]:
        """Find references (requires extension)."""
        self.logger.warning("find_references requires VS Code extension")
        return []

    async def go_to_definition(self, path: str, position: Position) -> tuple[str, Position] | None:
        """Go to definition (requires extension)."""
        self.logger.warning("go_to_definition requires VS Code extension")
        return None

    async def get_completions(self, path: str, position: Position) -> list[CompletionItem]:
        """Get completions (requires extension)."""
        self.logger.warning("get_completions requires VS Code extension")
        return []

    # ═══════════════════════════════════════════════════════════════
    # Commands
    # ═══════════════════════════════════════════════════════════════

    async def execute_command(self, command: IDECommand) -> Any:
        """Execute a VS Code command."""
        return await self._run_cli_command("--command", command.command)

    async def get_available_commands(self) -> list[str]:
        """Get available commands."""
        return list(self.COMMANDS.keys())

    async def _run_cli_command(self, *args: str) -> bool:
        """Run a VS Code CLI command."""
        if not self.cli_path:
            return False

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [self.cli_path, *args],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"CLI command failed: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════
    # Terminal
    # ═══════════════════════════════════════════════════════════════

    async def run_in_terminal(self, command: str, name: str | None = None) -> bool:
        """Run command in VS Code terminal."""
        if not self.cli_path:
            return False

        # Open a new terminal and run the command
        # This is limited without extension - we can only open the terminal
        try:
            # Try to use VS Code's integrated terminal via extension
            await self._run_cli_command("--command", "workbench.action.terminal.new")
            # Would need extension to actually send the command
            self.logger.info(f"Terminal opened. Run manually: {command}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to open terminal: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════
    # Notifications
    # ═══════════════════════════════════════════════════════════════

    async def show_message(self, message: str, level: str = "info") -> None:
        """Show message (limited without extension)."""
        self.logger.info(f"[VS Code Message] {message}")

    async def show_input(self, prompt: str, default: str | None = None) -> str | None:
        """Show input (requires extension)."""
        self.logger.warning("show_input requires VS Code extension")
        return None

    # ═══════════════════════════════════════════════════════════════
    # Utility Methods
    # ═══════════════════════════════════════════════════════════════

    async def diff_files(self, path1: str, path2: str) -> bool:
        """Open diff view for two files."""
        if not self.cli_path:
            return False

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [self.cli_path, "--diff", path1, path2],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Diff failed: {e}")
            return False

    async def install_extension(self, extension_id: str) -> bool:
        """Install a VS Code extension."""
        if not self.cli_path:
            return False

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [self.cli_path, "--install-extension", extension_id],
                capture_output=True,
                timeout=120,
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Extension install failed: {e}")
            return False

    async def list_extensions(self) -> list[str]:
        """List installed extensions."""
        if not self.cli_path:
            return []

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [self.cli_path, "--list-extensions"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout.strip().splitlines()
        except Exception as e:
            self.logger.error(f"List extensions failed: {e}")

        return []


__all__ = ["VSCodeAdapter"]
