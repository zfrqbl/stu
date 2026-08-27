"""ConnectionManager: manages MCP server connection lifecycle."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from ..config import McpConfig, MCPServerConfig
from .transport import MCPTransport, MockMCPTransport, StdioMCPTransport, MCPToolDefinition
from .schema_validator import SchemaValidator
from .sandbox_interceptor import SandboxInterceptor
from .execution_wrapper import ExecutionWrapper


class MCPServerConnection:
    """Represents a single MCP server connection."""

    def __init__(self, config: MCPServerConfig, transport: MCPTransport):
        self.config = config
        self.transport = transport
        self.status: str = "disconnected"
        self.last_error: str | None = None
        self.tools: list[MCPToolDefinition] = []
        self.tool_validation: dict[str, Any] = {}

    @property
    def tools_count(self) -> int:
        return len(self.tools)


class ConnectionManager:
    """Manages all MCP server connections."""

    def __init__(
        self,
        config: McpConfig,
        schema_validator: SchemaValidator,
        interceptor: SandboxInterceptor,
    ):
        self.config = config
        self.schema_validator = schema_validator
        self.execution_wrapper = ExecutionWrapper(
            interceptor=interceptor,
            default_timeout=config.connection_timeout_seconds,
        )
        self._connections: dict[str, MCPServerConnection] = {}

    def _create_transport(self, server_config: MCPServerConfig) -> MCPTransport:
        if server_config.transport == "mock":
            tools_data = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in server_config.tools
            ]
            return MockMCPTransport(server_config.name, tools_data)

        if server_config.transport == "stdio":
            if not self.config.allow_local_stdio:
                raise ValueError("Local stdio transport is disabled by configuration")

            if server_config.command not in self.config.allowed_stdio_commands:
                raise ValueError(
                    f"Command '{server_config.command}' is not in allowed_stdio_commands"
                )

            return StdioMCPTransport(
                server_name=server_config.name,
                command=server_config.command or "",
                args=server_config.args,
                env=server_config.env,
            )

        raise ValueError(f"Unsupported transport: {server_config.transport}")

    async def connect_all(self) -> None:
        if not self.config.enabled:
            logger.info("MCP is disabled, skipping connections")
            return

        for server_config in self.config.servers:
            if not server_config.enabled:
                logger.debug(f"MCP server '{server_config.name}' is disabled, skipping")
                continue

            try:
                await self.connect_server(server_config)
            except Exception as e:
                logger.error(f"Failed to connect MCP server '{server_config.name}': {e}")
                connection = MCPServerConnection(
                    server_config,
                    MockMCPTransport(server_config.name, []),
                )
                connection.status = "error"
                connection.last_error = str(e)
                self._connections[server_config.name] = connection

    async def connect_server(self, server_config: MCPServerConfig) -> None:
        transport = self._create_transport(server_config)
        connection = MCPServerConnection(server_config, transport)

        try:
            await transport.connect()
            connection.status = "connected"

            tools = await transport.list_tools()
            validation_results = self.schema_validator.validate_tools(tools)

            valid_tools = []
            for tool in tools:
                validation = validation_results.get(tool.name)
                if validation and validation.valid:
                    valid_tools.append(tool)
                    connection.tool_validation[tool.name] = {
                        "valid": True,
                        "error": None,
                    }
                else:
                    connection.tool_validation[tool.name] = {
                        "valid": False,
                        "error": validation.error if validation else "Unknown error",
                    }
                    if not self.config.strict_schema_validation:
                        valid_tools.append(tool)

            connection.tools = valid_tools
            self._connections[server_config.name] = connection
            logger.info(
                f"MCP server '{server_config.name}' connected with {len(valid_tools)} tools"
            )
        except Exception as e:
            connection.status = "error"
            connection.last_error = str(e)
            self._connections[server_config.name] = connection
            raise

    async def disconnect_all(self) -> None:
        for name, connection in self._connections.items():
            try:
                await connection.transport.disconnect()
                connection.status = "disconnected"
            except Exception as e:
                logger.warning(f"Error disconnecting MCP server '{name}': {e}")

    def get_connection(self, server_name: str) -> MCPServerConnection | None:
        return self._connections.get(server_name)

    def get_all_connections(self) -> list[MCPServerConnection]:
        return list(self._connections.values())

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        project_id: str,
    ):
        connection = self._connections.get(server_name)
        if not connection:
            from ..models import ToolInvokeResponse
            from ..constants import ToolExecutionStatus

            return ToolInvokeResponse(
                tool_name=f"mcp_{server_name}_{tool_name}",
                status=ToolExecutionStatus.ERROR,
                output=None,
                error=f"MCP server '{server_name}' not found",
                duration_ms=0,
            )

        timeout = connection.config.timeout_seconds or self.config.connection_timeout_seconds

        return await self.execution_wrapper.execute(
            transport=connection.transport,
            server_name=server_name,
            tool_name=tool_name,
            arguments=arguments,
            project_id=project_id,
            timeout=timeout,
        )
