"""Memory API router."""

from fastapi import APIRouter, HTTPException, Request, Query
from ..models import MemoryCreateRequest, MemoryReadResponse, MemorySearchResult

router = APIRouter(prefix="/projects/{project_id}/memory", tags=["memory"])

@router.get("", response_model=list[MemoryReadResponse])
def list_memories(project_id: str, request: Request, query: str | None = Query(None)):
    _ensure_project_exists(request, project_id)
    return request.app.state.memory_service.list_memories(project_id, query)

@router.post("", response_model=MemoryReadResponse, status_code=201)
def create_memory(project_id: str, req: MemoryCreateRequest, request: Request):
    _ensure_project_exists(request, project_id)
    try:
        return request.app.state.memory_service.create_memory(project_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/search", response_model=list[MemorySearchResult])
def search_memories(project_id: str, request: Request, query: str = Query(..., min_length=1)):
    _ensure_project_exists(request, project_id)
    return request.app.state.memory_service.search_memory(project_id, query)

@router.get("/{memory_id}", response_model=MemoryReadResponse)
def get_memory(project_id: str, memory_id: str, request: Request):
    _ensure_project_exists(request, project_id)
    mem = request.app.state.memory_service.get_memory(project_id, memory_id)
    if not mem: raise HTTPException(status_code=404, detail="Memory not found")
    return mem

@router.delete("/{memory_id}", status_code=204)
def delete_memory(project_id: str, memory_id: str, request: Request):
    _ensure_project_exists(request, project_id)
    deleted = request.app.state.memory_service.delete_memory(project_id, memory_id)
    if not deleted: raise HTTPException(status_code=404, detail="Memory not found")

def _ensure_project_exists(request: Request, project_id: str):
    if not request.app.state.project_service.get_project(project_id):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
