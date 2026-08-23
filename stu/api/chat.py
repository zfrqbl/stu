"""Chat API router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..models import ChatMessage, ChatRequest, ChatResponse

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def send_message(project_id: str, req: ChatRequest, request: Request):
    _ensure_project_exists(request, project_id)
    chat_service = request.app.state.chat_service
    try:
        return await chat_service.send_message(project_id, req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=list[ChatMessage])
def get_history(project_id: str, request: Request):
    _ensure_project_exists(request, project_id)
    return request.app.state.chat_service.get_history(project_id)


def _ensure_project_exists(request: Request, project_id: str) -> None:
    if not request.app.state.project_service.get_project(project_id):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
