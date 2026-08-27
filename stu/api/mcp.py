"""MCP API router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..models import MCPServerSummary, MCPToolInfo

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/servers", response_model=list[MCPServerSummary])
def list_mcp_servers(request: Request):
    manager = getattr(request.app.state, "mcp_connection_manager", None)
    if not manager:
        return []

    summaries = []
    for connection in manager.get_all_connections():
        summaries.append(
            MCPServerSummary(
                name=connection.config.name,
                transport=connection.config.transport,
                enabled=connection.config.enabled,
                status=connection.status,
                tools_count=connection.tools_count,
                last_error=connection.last_error,
            )
        )
    return summaries


@router.get("/servers/{server_name}/tools", response_model=list[MCPToolInfo])
def list_mcp_server_tools(server_name: str, request: Request):
    manager = getattr(request.app.state, "mcp_connection_manager", None)
    if not manager:
        raise HTTPException(status_code=404, detail="MCP is not configured")

    connection = manager.get_connection(server_name)
    if not connection:
        raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found")

    tools = []
    for tool in connection.tools:
        validation = connection.tool_validation.get(tool.name, {})
        tools.append(
            MCPToolInfo(
                server_name=server_name,
                tool_name=tool.name,
                full_name=f"mcp_{server_name}_{tool.name}",
                description=tool.description,
                input_schema=tool.input_schema,
                schema_valid=validation.get("valid", True),
                schema_error=validation.get("error"),
            )
        )
    return tools
