"""SandboxInterceptor: validates MCP tool calls against security policies."""

from __future__ import annotations

from typing import Any

from loguru import logger

from ..constants import SecurityDecision
from ..security.guardrails import GuardrailOrchestrator


class SandboxInterceptor:
    """Intercepts MCP tool calls and enforces sandbox boundaries."""

    def __init__(self, guardrails: GuardrailOrchestrator):
        self.guardrails = guardrails

    def intercept(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        project_id: str,
    ) -> tuple[bool, str | None]:
        full_tool_name = f"mcp_{server_name}_{tool_name}"

        check = self.guardrails.pre_tool(full_tool_name, arguments, project_id)

        if check.decision == SecurityDecision.DENY:
            logger.warning(
                f"SandboxInterceptor blocked MCP tool '{full_tool_name}': {check.reason}"
            )
            return False, check.reason or "Blocked by security guardrails"

        return True, None

    def intercept_output(
        self,
        server_name: str,
        tool_name: str,
        output: Any,
        project_id: str,
    ) -> tuple[bool, str | None]:
        full_tool_name = f"mcp_{server_name}_{tool_name}"

        check = self.guardrails.post_tool(full_tool_name, output, project_id)

        if check.decision == SecurityDecision.DENY:
            logger.warning(
                f"SandboxInterceptor blocked MCP output from '{full_tool_name}': {check.reason}"
            )
            return False, check.reason or "Blocked by post-tool security guardrails"

        return True, None
