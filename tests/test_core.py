"""
Tests for the core JARVIS modules.
"""

import pytest
from pathlib import Path


class TestCoreImports:
    """Test that all core modules can be imported."""

    def test_import_config(self):
        from jarvis.config import Settings
        assert Settings is not None

    def test_import_exceptions(self):
        from jarvis.core.exceptions import (
            JarvisError,
            ToolNotFoundError,
            ToolExecutionError,
            ConfigurationError,
        )
        assert JarvisError is not None
        assert ToolNotFoundError is not None

    def test_import_logging(self):
        from jarvis.core.logging import get_logger
        logger = get_logger("test")
        assert logger is not None


class TestToolRegistry:
    """Test the tool registry functionality."""

    def test_import_registry(self):
        from jarvis.tools.registry import ToolRegistry
        assert ToolRegistry is not None

    def test_registry_singleton(self):
        from jarvis.tools.registry import ToolRegistry
        r1 = ToolRegistry()
        r2 = ToolRegistry()
        # Both should be same instance (singleton)
        assert r1 is r2

    def test_list_tools(self):
        from jarvis.tools.registry import ToolRegistry
        registry = ToolRegistry()
        tools = registry.list_tools()
        assert isinstance(tools, list)


class TestToolSchema:
    """Test tool schema definitions."""

    def test_import_schema(self):
        from jarvis.tools.schema import ToolParameter, ToolSchema
        assert ToolParameter is not None
        assert ToolSchema is not None

    def test_create_parameter(self):
        from jarvis.tools.schema import ToolParameter
        param = ToolParameter(
            name="test_param",
            param_type="string",
            description="A test parameter",
            required=True,
        )
        assert param.name == "test_param"
        assert param.required is True

    def test_create_schema(self):
        from jarvis.tools.schema import ToolParameter, ToolSchema
        schema = ToolSchema(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(
                    name="input",
                    param_type="string",
                    description="Input value",
                    required=True,
                )
            ],
        )
        assert schema.name == "test_tool"
        assert len(schema.parameters) == 1


class TestBuiltinTools:
    """Test builtin tools are available."""

    def test_import_file_tools(self):
        from jarvis.tools.builtin.file import FileReadTool, FileWriteTool
        assert FileReadTool is not None
        assert FileWriteTool is not None

    def test_import_shell_tools(self):
        from jarvis.tools.builtin.shell import ShellExecuteTool
        assert ShellExecuteTool is not None

    def test_import_git_tools(self):
        from jarvis.tools.builtin.git import GitStatusTool, GitCommitTool
        assert GitStatusTool is not None

    def test_import_system_tools(self):
        from jarvis.tools.builtin.system import SystemInfoTool
        assert SystemInfoTool is not None
