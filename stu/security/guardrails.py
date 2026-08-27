"""GuardrailOrchestrator: centralized security enforcement."""

from __future__ import annotations

from typing import Any

from ..config import SecurityConfig
from ..constants import SecurityDecision
from ..models import SecurityCheckResult, SecurityEvent, SecuritySeverity
from .egress import EgressGuard
from .events import SecurityEventStore
from .sanitizer import SkillSanitizer


class GuardrailOrchestrator:
    def __init__(
        self,
        config: SecurityConfig,
        sanitizer: SkillSanitizer,
        egress: EgressGuard,
        event_store: SecurityEventStore,
    ):
        self.config = config
        self.sanitizer = sanitizer
        self.egress = egress
        self.event_store = event_store

    def _allow(self, source: str = "guardrails") -> SecurityCheckResult:
        return SecurityCheckResult(
            decision=SecurityDecision.ALLOW,
            source=source,
            severity=SecuritySeverity.LOW,
            reason=None,
        )

    def _finalize(self, result: SecurityCheckResult) -> SecurityCheckResult:
        if result.decision == SecurityDecision.REVIEW and self.config.policy.block_on_review:
            return SecurityCheckResult(
                decision=SecurityDecision.DENY,
                source=result.source,
                severity=result.severity,
                reason=result.reason or "Blocked because review decisions are treated as deny.",
                metadata=result.metadata,
            )
        return result

    def _record(
        self,
        result: SecurityCheckResult,
        project_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        if result.decision == SecurityDecision.ALLOW and not self.config.policy.record_allow_events:
            return

        event = SecurityEvent(
            project_id=project_id,
            source=result.source,
            decision=result.decision,
            severity=result.severity,
            reason=result.reason or "",
            context=context or {},
        )
        self.event_store.record(event)

    def pre_loop(self, goal: str, project_id: str) -> SecurityCheckResult:
        if not self.config.enable_guardrails:
            return self._allow("guardrails.pre_loop")

        result = self.sanitizer.scan_text(goal, source="guardrails.pre_loop")
        result = self._finalize(result)
        self._record(result, project_id=project_id, context={"hook": "pre_loop"})
        return result

    def pre_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        project_id: str,
    ) -> SecurityCheckResult:
        if not self.config.enable_guardrails:
            return self._allow("guardrails.pre_tool")

        result = self.sanitizer.scan_tool_arguments(tool_name, arguments)
        result = self._finalize(result)

        if result.decision != SecurityDecision.ALLOW:
            self._record(result, project_id=project_id, context={"hook": "pre_tool", "tool_name": tool_name})
            return result

        if isinstance(arguments, dict):
            for key, value in arguments.items():
                if not isinstance(value, str):
                    continue

                if key.lower() not in {"url", "uri", "endpoint", "host"}:
                    continue

                if not value.startswith(("http://", "https://")):
                    continue

                egress_result = self.egress.authorize_url(value)
                egress_result = self._finalize(egress_result)

                if egress_result.decision != SecurityDecision.ALLOW:
                    self._record(
                        egress_result,
                        project_id=project_id,
                        context={"hook": "pre_tool", "tool_name": tool_name, "field": key},
                    )
                    return egress_result

        return self._allow("guardrails.pre_tool")

    def post_tool(
        self,
        tool_name: str,
        output: Any,
        project_id: str,
    ) -> SecurityCheckResult:
        if not self.config.enable_guardrails:
            return self._allow("guardrails.post_tool")

        result = self.sanitizer.scan_output(tool_name, output)
        result = self._finalize(result)
        self._record(result, project_id=project_id, context={"hook": "post_tool", "tool_name": tool_name})
        return result

    def post_loop(self, project_id: str) -> SecurityCheckResult:
        return self._allow("guardrails.post_loop")
