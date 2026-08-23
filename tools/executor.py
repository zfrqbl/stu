"""Tool Executor with timeout, validation, and output limits."""

from __future__ import annotations

import asyncio
import json
import time

from pydantic import ValidationError

from ..config import ToolsConfig
from ..constants import ToolExecutionStatus
from ..models import ToolInvokeResponse
from .catalog import ToolCatalog
from .context import ToolContext


class ToolExecutor:
    def __init__(self, catalog: ToolCatalog, config: ToolsConfig):
        self.catalog = catalog
        self.config = config

    async def invoke(
        self,
        tool_name: str,
        arguments: dict,
        context: ToolContext,
    ) -> ToolInvokeResponse:
        start = time.perf_counter()

        if not self.config.enabled:
            return self._response(
                tool_name,
                ToolExecutionStatus.BLOCKED,
                start,
                error="Tool execution is disabled.",
            )

        descriptor = self.catalog.get_enabled_descriptor(tool_name)
        if not descriptor:
            return self._response(
                tool_name,
                ToolExecutionStatus.BLOCKED,
                start,
                error="Tool not found or disabled.",
            )

        impl = self.catalog.get_implementation(tool_name)
        arg_model = self.catalog.get_arg_model(tool_name)

        if not impl or not arg_model:
            return self._response(
                tool_name,
                ToolExecutionStatus.ERROR,
                start,
                error="Tool implementation is incomplete.",
            )

        try:
            parsed_args = arg_model.model_validate(arguments)
        except ValidationError as exc:
            return self._response(
                tool_name,
                ToolExecutionStatus.ERROR,
                start,
                error=str(exc),
            )

        try:
            raw_output = await asyncio.wait_for(
                asyncio.to_thread(impl, parsed_args, context),
                timeout=self.config.default_timeout_seconds,
            )
        except asyncio.TimeoutError:
            return self._response(
                tool_name,
                ToolExecutionStatus.TIMEOUT,
                start,
                error="Tool execution timed out.",
            )
        except Exception as exc:
            return self._response(
                tool_name,
                ToolExecutionStatus.ERROR,
                start,
                error=str(exc),
            )

        output = self._truncate(raw_output)

        return self._response(
            tool_name,
            ToolExecutionStatus.SUCCESS,
            start,
            output=output,
        )

    def _response(
        self,
        tool_name: str,
        status: ToolExecutionStatus,
        start: float,
        output=None,
        error: str | None = None,
    ) -> ToolInvokeResponse:
        duration_ms = (time.perf_counter() - start) * 1000.0
        return ToolInvokeResponse(
            tool_name=tool_name,
            status=status,
            output=output,
            error=error,
            duration_ms=duration_ms,
        )

    def _truncate(self, output):
        max_bytes = self.config.max_output_bytes

        try:
            serialized = json.dumps(output, ensure_ascii=False, default=str)
        except Exception:
            serialized = str(output)

        encoded = serialized.encode("utf-8")
        if len(encoded) <= max_bytes:
            return output

        preview = encoded[:max_bytes].decode("utf-8", errors="replace")
        return {
            "truncated": True,
            "preview": preview,
        }
