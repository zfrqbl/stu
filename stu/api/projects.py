"""Project API router."""

from fastapi import APIRouter, HTTPException, Request
from ..models import ProjectSummary, ProjectCreateRequest, Project

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get("", response_model=list[ProjectSummary])
def list_projects(request: Request):
    return request.app.state.project_service.list_projects()

@router.post("", response_model=Project, status_code=201)
def create_project(req: ProjectCreateRequest, request: Request):
    try:
        return request.app.state.project_service.create_project(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str, request: Request):
    proj = request.app.state.project_service.get_project(project_id)
    if not proj: raise HTTPException(status_code=404, detail="Project not found")
    return proj
