"""ExecutionWrapper: wraps MCP tool execution with timeout and error handling."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from ..models import ToolInvokeResponse
from ..constants import ToolExecutionStatus
from .sandbox_interceptor import SandboxInterceptor
from .transport import MCPTransport, MCPToolResult


class ExecutionWrapper:
    """Wraps MCP tool calls with timeout, guardrails, and structured errors."""

    def __init__(
        self,
        interceptor: SandboxInterceptor,
        default_timeout: float = 60.0,
    ):
        self.interceptor = interceptor
        self.default_timeout = default_timeout

    async def execute(
        self,
        transport: MCPTransport,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        project_id: str,
        timeout: float | None = None,
    ) -> ToolInvokeResponse:
        start = time.perf_counter()
        effective_timeout = timeout or self.default_timeout
        full_tool_name = f"mcp_{server_name}_{tool_name}"

        allowed, reason = self.interceptor.intercept(
            server_name, tool_name, arguments, project_id
        )
        if not allowed:
            return ToolInvokeResponse(
                tool_name=full_tool_name,
                status=ToolExecutionStatus.BLOCKED,
                output=None,
                error=reason,
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        if not transport.is_connected:
            return ToolInvokeResponse(
                tool_name=full_tool_name,
                status=ToolExecutionStatus.ERROR,
                output=None,
                error="MCP transport is not connected",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        try:
            result: MCPToolResult = await asyncio.wait_for(
                transport.call_tool(tool_name, arguments),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            return ToolInvokeResponse(
                tool_name=full_tool_name,
                status=ToolExecutionStatus.TIMEOUT,
                output=None,
                error=f"MCP tool call timed out after {effective_timeout}s",
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return ToolInvokeResponse(
                tool_name=full_tool_name,
                status=ToolExecutionStatus.ERROR,
                output=None,
                error=f"MCP tool call failed: {e}",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        if result.is_error:
            return ToolInvokeResponse(
                tool_name=full_tool_name,
                status=ToolExecutionStatus.ERROR,
                output=None,
                error=str(result.content),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        output_allowed, output_reason = self.interceptor.intercept_output(
            server_name, tool_name, result.content, project_id
        )
        if not output_allowed:
            return ToolInvokeResponse(
                tool_name=full_tool_name,
                status=ToolExecutionStatus.BLOCKED,
                output=None,
                error=output_reason,
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        return ToolInvokeResponse(
            tool_name=full_tool_name,
            status=ToolExecutionStatus.SUCCESS,
            output=result.content,
            error=None,
            duration_ms=(time.perf_counter() - start) * 1000,
        )
