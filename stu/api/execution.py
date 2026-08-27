"""Execution API router."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from ..constants import SecurityDecision
from ..models import ExecutionStartRequest, LoopState, LoopStatus, LoopPhase

router = APIRouter(prefix="/projects/{project_id}/execution", tags=["execution"])


@router.post("/start", response_model=LoopState)
async def start_execution(project_id: str, req: ExecutionStartRequest, request: Request):
    _ensure_project_exists(request, project_id)

    guardrails = getattr(request.app.state, "guardrails", None)
    if guardrails:
        check = guardrails.pre_loop(req.goal, project_id)
        if check.decision == SecurityDecision.DENY:
            raise HTTPException(
                status_code=403,
                detail=check.reason or "Blocked by security guardrails.",
            )

    orchestrator = request.app.state.orchestrator
    state = await orchestrator.start_loop(project_id, req.goal)
    return state


@router.get("/status", response_model=LoopState)
async def get_execution_status(project_id: str, request: Request):
    _ensure_project_exists(request, project_id)
    state_manager = request.app.state.state_manager
    state = state_manager.load_state()
    if not state or state.project_id != project_id:
        return LoopState(
            loop_id="none",
            project_id=project_id,
            status=LoopStatus.IDLE,
            current_phase=LoopPhase.INTAKE,
            goal="",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    return state


@router.post("/approve", response_model=LoopState)
async def approve_execution(project_id: str, request: Request):
    _ensure_project_exists(request, project_id)
    orchestrator = request.app.state.orchestrator
    state = orchestrator.state_manager.load_state()
    if not state or state.project_id != project_id:
        raise HTTPException(status_code=404, detail="No active loop found")
    state = await orchestrator.resume_loop(state, approved=True)
    return state


@router.post("/reject", response_model=LoopState)
async def reject_execution(project_id: str, request: Request):
    _ensure_project_exists(request, project_id)
    orchestrator = request.app.state.orchestrator
    state = orchestrator.state_manager.load_state()
    if not state or state.project_id != project_id:
        raise HTTPException(status_code=404, detail="No active loop found")
    state = await orchestrator.resume_loop(state, approved=False)
    return state


def _ensure_project_exists(request: Request, project_id: str) -> None:
    if not request.app.state.project_service.get_project(project_id):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
