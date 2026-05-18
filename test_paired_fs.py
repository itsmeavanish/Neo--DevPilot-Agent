"""Smoke tests for paired path resolution and tool registration."""

import tempfile
from pathlib import Path

from jarvis.tools.builtin.paired_path import resolve_paired_path
from jarvis.tools.registry import tool_registry


def test_resolve_relative_under_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sub = root / "src"
        sub.mkdir()
        f = sub / "a.py"
        f.write_text("x", encoding="utf-8")

        resolved, err = resolve_paired_path("src/a.py", str(root))
        assert err is None
        assert resolved is not None
        assert Path(resolved).name == "a.py"


def test_reject_escape_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        resolved, err = resolve_paired_path("..", str(root))
        assert resolved is None
        assert err is not None


def test_paired_tools_registered():
    names = {t.name for t in tool_registry.get_all()}
    assert "paired_read_file" in names
    assert "paired_write_file" in names
    assert "paired_list_directory" in names


if __name__ == "__main__":
    test_resolve_relative_under_workspace()
    test_reject_escape_workspace()
    test_paired_tools_registered()
    print("ok")
