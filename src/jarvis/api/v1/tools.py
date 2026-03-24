"""
Tools API endpoints.

List and interact with registered tools.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from jarvis.tools import ToolRegistry, ToolResult
from jarvis.api.deps import get_tool_registry

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# Response Models
# ═══════════════════════════════════════════════════════════════

class ToolInfo(BaseModel):
    """Information about a tool."""
    name: str
    description: str
    risk_level: str
    requires_approval: bool
    timeout: int
    schema: dict


class ToolExecuteRequest(BaseModel):
    """Request to execute a tool."""
    params: dict[str, Any] = Field(default_factory=dict)


class ToolExecuteResponse(BaseModel):
    """Response from tool execution."""
    status: str
    output: Any = None
    error: str | None = None
    metadata: dict = {}


# ═══════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("", response_model=list[ToolInfo])
async def list_tools(
    registry: ToolRegistry = Depends(get_tool_registry),
):
    """
    List all registered tools.

    Returns information about each tool including its schema.
    """
    tools = []
    for tool in registry.get_all():
        tools.append(ToolInfo(
            name=tool.name,
            description=tool.description,
            risk_level=tool.risk_level.name,
            requires_approval=tool.requires_approval,
            timeout=tool.timeout,
            schema=tool.schema,
        ))

    return sorted(tools, key=lambda t: t.name)


@router.get("/{tool_name}", response_model=ToolInfo)
async def get_tool(
    tool_name: str,
    registry: ToolRegistry = Depends(get_tool_registry),
):
    """
    Get details about a specific tool.

    Returns the tool's schema and configuration.
    """
    if not registry.has(tool_name):
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

    tool = registry.get(tool_name)
    return ToolInfo(
        name=tool.name,
        description=tool.description,
        risk_level=tool.risk_level.name,
        requires_approval=tool.requires_approval,
        timeout=tool.timeout,
        schema=tool.schema,
    )


@router.post("/{tool_name}/execute", response_model=ToolExecuteResponse)
async def execute_tool(
    tool_name: str,
    request: ToolExecuteRequest,
    registry: ToolRegistry = Depends(get_tool_registry),
):
    """
    Execute a tool directly.

    Bypasses the agent planning system for direct tool execution.
    """
    if not registry.has(tool_name):
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

    tool = registry.get(tool_name)

    # Validate parameters
    errors = tool.validate_params(request.params)
    if errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "Invalid parameters", "errors": errors}
        )

    # Execute
    result = await tool.execute(request.params)

    return ToolExecuteResponse(
        status=result.status,
        output=result.output,
        error=result.error,
        metadata=result.metadata,
    )


@router.get("/{tool_name}/schema")
async def get_tool_schema(
    tool_name: str,
    registry: ToolRegistry = Depends(get_tool_registry),
):
    """
    Get the JSON schema for a tool.

    Returns the schema in OpenAI function calling format.
    """
    if not registry.has(tool_name):
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

    tool = registry.get(tool_name)
    return tool.get_schema_for_llm()


@router.get("/schemas/all")
async def get_all_schemas(
    registry: ToolRegistry = Depends(get_tool_registry),
):
    """
    Get all tool schemas for LLM function calling.

    Returns schemas in OpenAI-compatible format.
    """
    return {"tools": registry.get_schemas_for_llm()}


__all__ = ["router"]
