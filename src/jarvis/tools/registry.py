"""
Tool Registry for JARVIS.

Central registry for discovering and managing tools.
"""

from typing import Type, Iterator
from jarvis.tools.base import BaseTool
from jarvis.core.logging import get_logger
from jarvis.core.exceptions import ToolNotFoundError

logger = get_logger("jarvis.tools.registry")


class ToolRegistry:
    """
    Central registry for all available tools.

    Supports:
    - Registration via decorator
    - Discovery of built-in and plugin tools
    - Lookup by name
    - LLM function calling schema generation
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._tool_classes: dict[str, Type[BaseTool]] = {}

    def register(self, tool_class: Type[BaseTool]) -> Type[BaseTool]:
        """
        Register a tool class with the registry.

        Can be used as a decorator:

            @tool_registry.register
            class MyTool(BaseTool):
                ...
        """
        if not hasattr(tool_class, "name"):
            raise ValueError(f"Tool class {tool_class.__name__} missing 'name' attribute")

        name = tool_class.name
        if name in self._tool_classes:
            logger.warning(f"Overwriting existing tool: {name}")

        self._tool_classes[name] = tool_class
        logger.info(f"Registered tool: {name}")
        return tool_class

    def register_instance(self, tool: BaseTool) -> None:
        """Register an instantiated tool."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool instance: {tool.name}")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool instance: {tool.name}")

    def get(self, name: str) -> BaseTool:
        """
        Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance

        Raises:
            ToolNotFoundError: If tool doesn't exist
        """
        # Check for existing instance
        if name in self._tools:
            return self._tools[name]

        # Create instance from class
        if name in self._tool_classes:
            tool = self._tool_classes[name]()
            self._tools[name] = tool
            return tool

        raise ToolNotFoundError(name)

    def has(self, name: str) -> bool:
        """Check if a tool exists."""
        return name in self._tools or name in self._tool_classes

    def list_tools(self) -> list[str]:
        """Get list of all registered tool names."""
        return list(set(self._tools.keys()) | set(self._tool_classes.keys()))

    def get_all(self) -> Iterator[BaseTool]:
        """Iterate over all tool instances."""
        for name in self.list_tools():
            yield self.get(name)

    def get_schemas_for_llm(self) -> list[dict]:
        """
        Get all tool schemas in LLM function calling format.

        Returns:
            List of tool schemas for LLM consumption
        """
        schemas = []
        for tool in self.get_all():
            schemas.append(tool.get_schema_for_llm())
        return schemas

    def get_tool_info(self) -> list[dict]:
        """
        Get information about all registered tools.

        Returns:
            List of tool info dictionaries
        """
        info = []
        for tool in self.get_all():
            info.append({
                "name": tool.name,
                "description": tool.description,
                "risk_level": tool.risk_level.name,
                "requires_approval": tool.requires_approval,
                "timeout": tool.timeout,
                "schema": tool.schema,
            })
        return info

    def unregister(self, name: str) -> bool:
        """
        Remove a tool from the registry.

        Args:
            name: Tool name

        Returns:
            True if tool was removed, False if not found
        """
        removed = False
        if name in self._tools:
            del self._tools[name]
            removed = True
        if name in self._tool_classes:
            del self._tool_classes[name]
            removed = True
        return removed

    def clear(self) -> None:
        """Remove all tools from the registry."""
        self._tools.clear()
        self._tool_classes.clear()

    def __contains__(self, name: str) -> bool:
        return self.has(name)

    def __len__(self) -> int:
        return len(self.list_tools())

    def __repr__(self) -> str:
        return f"<ToolRegistry tools={self.list_tools()}>"


# Global tool registry instance
tool_registry = ToolRegistry()


def load_builtin_tools() -> None:
    from jarvis.tools.builtin import (
        shell,
        paired_shell,
        file,
        git,
        vscode,
        docker,
        process,
        log,
        system,
    )
        # Tools are auto-registered via decorator
    logger.info(f"Loaded {len(tool_registry)} built-in tools")


__all__ = ["ToolRegistry", "tool_registry", "load_builtin_tools"]
