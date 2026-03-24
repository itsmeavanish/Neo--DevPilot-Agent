"""
Tests for IDE integration.
"""

import pytest


class TestIDEImports:
    """Test IDE module imports."""

    def test_import_models(self):
        from jarvis.ide.models import (
            DiagnosticSeverity,
            Position,
            Range,
            Diagnostic,
            TextEdit,
            FileEdit,
        )
        assert DiagnosticSeverity is not None
        assert Diagnostic is not None
        assert FileEdit is not None

    def test_import_adapters(self):
        from jarvis.ide.adapters.base import BaseIDEAdapter
        from jarvis.ide.adapters.vscode import VSCodeAdapter
        from jarvis.ide.adapters.cursor import CursorAdapter
        assert BaseIDEAdapter is not None
        assert VSCodeAdapter is not None
        assert CursorAdapter is not None

    def test_import_manager(self):
        from jarvis.ide.manager import IDEManager
        assert IDEManager is not None


class TestIDEModels:
    """Test IDE model creation."""

    def test_create_position(self):
        from jarvis.ide.models import Position

        pos = Position(line=10, character=5)
        assert pos.line == 10
        assert pos.character == 5

    def test_create_range(self):
        from jarvis.ide.models import Position, Range

        range_obj = Range(
            start=Position(line=10, character=0),
            end=Position(line=10, character=20),
        )

        assert range_obj.start.line == 10
        assert range_obj.end.character == 20

    def test_create_diagnostic(self):
        from jarvis.ide.models import (
            Diagnostic,
            DiagnosticSeverity,
            Position,
            Range,
        )

        diagnostic = Diagnostic(
            file_path="/path/to/file.py",
            range=Range(
                start=Position(line=5, character=0),
                end=Position(line=5, character=10),
            ),
            severity=DiagnosticSeverity.ERROR,
            message="Undefined variable 'x'",
            source="pylint",
            code="E0602",
        )

        assert diagnostic.file_path == "/path/to/file.py"
        assert diagnostic.severity == DiagnosticSeverity.ERROR
        assert "undefined" in diagnostic.message.lower()

    def test_create_text_edit(self):
        from jarvis.ide.models import TextEdit, Position, Range

        edit = TextEdit(
            range=Range(
                start=Position(line=0, character=0),
                end=Position(line=0, character=5),
            ),
            new_text="hello",
        )

        assert edit.new_text == "hello"

    def test_create_file_edit(self):
        from jarvis.ide.models import FileEdit, TextEdit, Position, Range

        file_edit = FileEdit(
            file_path="/path/to/file.py",
            edits=[
                TextEdit(
                    range=Range(
                        start=Position(line=0, character=0),
                        end=Position(line=0, character=5),
                    ),
                    new_text="hello",
                )
            ],
        )

        assert file_edit.file_path == "/path/to/file.py"
        assert len(file_edit.edits) == 1


class TestIDEAdapters:
    """Test IDE adapter functionality."""

    def test_vscode_adapter_creation(self):
        from jarvis.ide.adapters.vscode import VSCodeAdapter

        adapter = VSCodeAdapter()
        assert adapter is not None
        assert adapter.name == "vscode"

    def test_cursor_adapter_creation(self):
        from jarvis.ide.adapters.cursor import CursorAdapter

        adapter = CursorAdapter()
        assert adapter is not None
        assert adapter.name == "cursor"

    def test_cursor_extends_vscode(self):
        from jarvis.ide.adapters.vscode import VSCodeAdapter
        from jarvis.ide.adapters.cursor import CursorAdapter

        cursor = CursorAdapter()
        assert isinstance(cursor, VSCodeAdapter)


class TestIDEManager:
    """Test IDE manager functionality."""

    def test_manager_creation(self):
        from jarvis.ide.manager import IDEManager

        manager = IDEManager()
        assert manager is not None

    def test_manager_singleton(self):
        from jarvis.ide.manager import get_ide_manager

        m1 = get_ide_manager()
        m2 = get_ide_manager()
        assert m1 is m2

    def test_list_available(self):
        from jarvis.ide.manager import IDEManager

        manager = IDEManager()
        available = manager.list_available()

        assert isinstance(available, list)

    def test_get_adapter(self):
        from jarvis.ide.manager import IDEManager
        from jarvis.ide.models import IDEType

        manager = IDEManager()
        adapter = manager.get_adapter(IDEType.VSCODE)

        # Adapter may or may not be available depending on system
        # Just verify the method works
        if adapter:
            assert adapter.name == "vscode"
