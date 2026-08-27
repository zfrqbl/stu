"""SkillSanitizer: regex and heuristic security scanning."""

from __future__ import annotations

import json
import re
from typing import Any

from ..config import SecurityConfig
from ..constants import SecurityDecision
from ..models import SecurityCheckResult, SecuritySeverity


class SkillSanitizer:
    def __init__(self, config: SecurityConfig):
        self.config = config

        self._forbidden_path_patterns = self._compile(config.forbidden_path_patterns)
        self._path_traversal_patterns = self._compile(config.path_traversal_patterns)
        self._forbidden_argument_patterns = self._compile(config.forbidden_argument_patterns)
        self._shell_command_patterns = self._compile(config.shell_command_patterns)
        self._secret_patterns = self._compile(config.secret_patterns)

    def _compile(self, patterns: list[str]) -> list[re.Pattern]:
        compiled = []
        for pattern in patterns:
            compiled.append(re.compile(pattern))
        return compiled

    def _truncate_bytes(self, text: str, max_bytes: int) -> tuple[str, bool]:
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) <= max_bytes:
            return text, False

        truncated = encoded[:max_bytes].decode("utf-8", errors="replace")
        return truncated, True

    def _scan_patterns(
        self,
        text: str,
        patterns: list[re.Pattern],
        reason: str,
        source: str,
    ) -> SecurityCheckResult | None:
        for pattern in patterns:
            if pattern.search(text):
                return SecurityCheckResult(
                    decision=SecurityDecision.DENY,
                    source=source,
                    severity=SecuritySeverity.HIGH,
                    reason=reason,
                )
        return None

    def scan_text(
        self,
        text: str,
        source: str = "sanitizer",
    ) -> SecurityCheckResult:
        if not self.config.enable_skill_sanitizer:
            return SecurityCheckResult(
                decision=SecurityDecision.ALLOW,
                source=source,
                severity=SecuritySeverity.LOW,
                reason=None,
            )

        if text is None:
            return SecurityCheckResult(
                decision=SecurityDecision.ALLOW,
                source=source,
                severity=SecuritySeverity.LOW,
                reason=None,
            )

        value = str(text)
        value, _ = self._truncate_bytes(value, self.config.max_argument_bytes)

        checks = [
            (self._path_traversal_patterns, "Path traversal pattern detected."),
            (self._forbidden_path_patterns, "Forbidden path pattern detected."),
            (self._shell_command_patterns, "Dangerous shell command pattern detected."),
            (self._forbidden_argument_patterns, "Forbidden argument pattern detected."),
            (self._secret_patterns, "Potential secret pattern detected."),
        ]

        for patterns, reason in checks:
            result = self._scan_patterns(value, patterns, reason, source)
            if result:
                return result

        return SecurityCheckResult(
            decision=SecurityDecision.ALLOW,
            source=source,
            severity=SecuritySeverity.LOW,
            reason=None,
        )

    def scan_tool_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> SecurityCheckResult:
        source = f"sanitizer.tool.{tool_name}"

        if not self.config.enable_skill_sanitizer:
            return SecurityCheckResult(
                decision=SecurityDecision.ALLOW,
                source=source,
                severity=SecuritySeverity.LOW,
                reason=None,
            )

        try:
            serialized = json.dumps(arguments, ensure_ascii=False, default=str)
        except Exception:
            serialized = str(arguments)

        encoded_len = len(serialized.encode("utf-8", errors="replace"))
        if encoded_len > self.config.max_argument_bytes:
            return SecurityCheckResult(
                decision=SecurityDecision.DENY,
                source=source,
                severity=SecuritySeverity.HIGH,
                reason="Tool arguments exceed max_argument_bytes.",
            )

        return self.scan_text(serialized, source=source)

    def scan_output(
        self,
        tool_name: str,
        output: Any,
    ) -> SecurityCheckResult:
        source = f"sanitizer.output.{tool_name}"

        if not self.config.enable_skill_sanitizer:
            return SecurityCheckResult(
                decision=SecurityDecision.ALLOW,
                source=source,
                severity=SecuritySeverity.LOW,
                reason=None,
            )

        try:
            serialized = json.dumps(output, ensure_ascii=False, default=str)
        except Exception:
            serialized = str(output)

        serialized, _ = self._truncate_bytes(serialized, self.config.max_output_scan_bytes)

        result = self._scan_patterns(
            serialized,
            self._secret_patterns,
            "Potential secret detected in tool output.",
            source,
        )

        if result:
            return result

        return SecurityCheckResult(
            decision=SecurityDecision.ALLOW,
            source=source,
            severity=SecuritySeverity.LOW,
            reason=None,
        )
