"""EgressGuard: network egress policy enforcement."""

from __future__ import annotations

from urllib.parse import urlparse

from ..config import SecurityConfig, ToolsConfig
from ..constants import SecurityDecision
from ..models import SecurityCheckResult, SecuritySeverity


class EgressGuard:
    def __init__(self, security_config: SecurityConfig, tools_config: ToolsConfig):
        self.security_config = security_config
        self.tools_config = tools_config

    @property
    def network_enabled(self) -> bool:
        return self.tools_config.allow_network

    def authorize_url(self, url: str) -> SecurityCheckResult:
        if not self.network_enabled:
            return SecurityCheckResult(
                decision=SecurityDecision.DENY,
                source="egress",
                severity=SecuritySeverity.HIGH,
                reason="Network egress is disabled.",
            )

        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            return SecurityCheckResult(
                decision=SecurityDecision.DENY,
                source="egress",
                severity=SecuritySeverity.HIGH,
                reason="Only http and https egress is allowed.",
            )

        host = parsed.hostname or ""
        if not host:
            return SecurityCheckResult(
                decision=SecurityDecision.DENY,
                source="egress",
                severity=SecuritySeverity.HIGH,
                reason="Egress URL has no host.",
            )

        for allowed in self.security_config.egress_allowlist:
            if host == allowed or host.endswith(f".{allowed}"):
                return SecurityCheckResult(
                    decision=SecurityDecision.ALLOW,
                    source="egress",
                    severity=SecuritySeverity.LOW,
                    reason=None,
                )

        return SecurityCheckResult(
            decision=SecurityDecision.DENY,
            source="egress",
            severity=SecuritySeverity.HIGH,
            reason=f"Host '{host}' is not in egress allowlist.",
        )
