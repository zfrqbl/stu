"""MCP transport abstraction layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class MCPToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolResult:
    content: Any
    is_error: bool = False


class MCPTransport(ABC):
    """Abstract base for MCP transports."""

    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def list_tools(self) -> list[MCPToolDefinition]:
        pass

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        pass


class MockMCPTransport(MCPTransport):
    """Mock transport for testing and offline development."""

    def __init__(self, server_name: str, tools: list[dict[str, Any]]):
        self._server_name = server_name
        self._tools = tools
        self._connected = False

    async def connect(self) -> None:
        self._connected = True
        logger.debug(f"MockMCPTransport '{self._server_name}' connected")

    async def disconnect(self) -> None:
        self._connected = False
        logger.debug(f"MockMCPTransport '{self._server_name}' disconnected")

    async def list_tools(self) -> list[MCPToolDefinition]:
        definitions = []
        for tool in self._tools:
            definitions.append(
                MCPToolDefinition(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    input_schema=tool.get("input_schema", {}),
                )
            )
        return definitions

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        if not self._connected:
            return MCPToolResult(content="Transport not connected", is_error=True)

        tool_names = [t["name"] for t in self._tools]
        if tool_name not in tool_names:
            return MCPToolResult(content=f"Tool '{tool_name}' not found", is_error=True)

        if tool_name == "echo":
            message = arguments.get("message", "")
            return MCPToolResult(content=f"Echo: {message}")

        if tool_name == "add":
            a = arguments.get("a", 0)
            b = arguments.get("b", 0)
            try:
                result = float(a) + float(b)
                return MCPToolResult(content=str(result))
            except (TypeError, ValueError) as e:
                return MCPToolResult(content=f"Math error: {e}", is_error=True)

        return MCPToolResult(content=f"Executed {tool_name} with {arguments}")

    @property
    def is_connected(self) -> bool:
        return self._connected


class StdioMCPTransport(MCPTransport):
    """Stdio transport using the mcp SDK. Feature-flagged for production use."""

    def __init__(self, server_name: str, command: str, args: list[str], env: dict[str, str]):
        self._server_name = server_name
        self._command = command
        self._args = args
        self._env = env
        self._connected = False
        self._session = None
        self._process = None

    async def connect(self) -> None:
        try:
            from mcp.client.stdio import stdio_client
            from mcp import ClientSession, StdioServerParameters

            server_params = StdioServerParameters(
                command=self._command,
                args=self._args,
                env=self._env or None,
            )

            self._client_context = stdio_client(server_params)
            read_stream, write_stream = await self._client_context.__aenter__()
            self._session = ClientSession(read_stream, write_stream)
            await self._session.__aenter__()
            await self._session.initialize()
            self._connected = True
            logger.info(f"StdioMCPTransport '{self._server_name}' connected")
        except Exception as e:
            logger.error(f"Failed to connect StdioMCPTransport '{self._server_name}': {e}")
            raise

    async def disconnect(self) -> None:
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
        if hasattr(self, "_client_context") and self._client_context:
            try:
                await self._client_context.__aexit__(None, None, None)
            except Exception:
                pass
        self._connected = False
        self._session = None
        logger.debug(f"StdioMCPTransport '{self._server_name}' disconnected")

    async def list_tools(self) -> list[MCPToolDefinition]:
        if not self._session:
            return []

        try:
            result = await self._session.list_tools()
            definitions = []
            for tool in result.tools:
                definitions.append(
                    MCPToolDefinition(
                        name=tool.name,
                        description=tool.description or "",
                        input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else {},
                    )
                )
            return definitions
        except Exception as e:
            logger.error(f"Failed to list tools from '{self._server_name}': {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        if not self._session:
            return MCPToolResult(content="Transport not connected", is_error=True)

        try:
            result = await self._session.call_tool(tool_name, arguments)
            content = result.content if hasattr(result, "content") else str(result)
            is_error = result.isError if hasattr(result, "isError") else False
            return MCPToolResult(content=content, is_error=is_error)
        except Exception as e:
            return MCPToolResult(content=f"Tool call failed: {e}", is_error=True)

    @property
    def is_connected(self) -> bool:
        return self._connected




