"""Security API router."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ..models import SecurityEvent, SecurityStatusResponse

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/events", response_model=list[SecurityEvent])
def list_security_events(
    request: Request,
    project_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    store = request.app.state.security_event_store
    return store.list(project_id=project_id, limit=limit)


@router.get("/status", response_model=SecurityStatusResponse)
def security_status(request: Request):
    config = request.app.state.config
    store = request.app.state.security_event_store
    counts = store.counts()

    return SecurityStatusResponse(
        guardrails_enabled=config.security.enable_guardrails,
        sanitizer_enabled=config.security.enable_skill_sanitizer,
        network_enabled=config.tools.allow_network,
        egress_allowlist=config.security.egress_allowlist,
        event_retention=config.security.event_retention,
        total_events=counts["total"],
        deny_count=counts["deny"],
        review_count=counts["review"],
    )
