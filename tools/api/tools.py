"""Tools API router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..models import (
    ToolDescriptor,
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolSearchResult,
)
from ..tools.context import build_tool_context

router = APIRouter(tags=["tools"])


@router.get("/tools", response_model=list[ToolDescriptor])
def list_tools(request: Request):
    return request.app.state.tool_catalog.list_tools(include_disabled=True)


@router.get("/tools/search", response_model=list[ToolSearchResult])
def search_tools(request: Request, query: str = Query(..., min_length=1)):
    selected = request.app.state.tool_rag.select_tools(query)
    return [ToolSearchResult(tool=descriptor, score=None) for descriptor in selected]


@router.post("/projects/{project_id}/tools/invoke", response_model=ToolInvokeResponse)
async def invoke_tool(project_id: str, req: ToolInvokeRequest, request: Request):
    _ensure_project_exists(request, project_id)

    context = build_tool_context(
        project_id=project_id,
        config=request.app.state.config,
        workspace_root=request.app.state.workspace.root,
        project_service=request.app.state.project_service,
        memory_service=request.app.state.memory_service,
        state_manager=request.app.state.state_manager,
    )

    return await request.app.state.tool_executor.invoke(
        req.tool_name,
        req.arguments,
        context,
    )


def _ensure_project_exists(request: Request, project_id: str) -> None:
    if not request.app.state.project_service.get_project(project_id):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
