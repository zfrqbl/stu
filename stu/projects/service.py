"""Project management service."""

from __future__ import annotations

import json
from pathlib import Path
from loguru import logger
from ..config import AppConfig
from ..models import Project, ProjectSummary, ProjectCreateRequest, ProjectPaths
from ..constants import ProjectScope
from ..workspace import get_project_paths, _ensure_directory

class ProjectService:
    def __init__(self, workspace_root: Path, config: AppConfig):
        self.root = workspace_root
        self.config = config

    def _get_paths(self, project_id: str) -> ProjectPaths:
        return get_project_paths(self.root, project_id, self.config)

    def list_projects(self) -> list[ProjectSummary]:
        projects_dir = self.root / self.config.workspace.projects_dir
        if not projects_dir.exists(): return []
        
        summaries = []
        for p in projects_dir.iterdir():
            if p.is_dir():
                meta_file = p / "project.json"
                if meta_file.exists():
                    try:
                        data = json.loads(meta_file.read_text(encoding="utf-8"))
                        proj = Project.model_validate(data)
                        summaries.append(ProjectSummary(
                            id=proj.id, name=proj.name, description=proj.description, created_at=proj.created_at
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to parse project metadata for {p.name}: {e}")
        return summaries

    def get_project(self, project_id: str) -> Project | None:
        paths = self._get_paths(project_id)
        if not paths.metadata_file.exists(): return None
        data = json.loads(paths.metadata_file.read_text(encoding="utf-8"))
        return Project.model_validate(data)

    def create_project(self, req: ProjectCreateRequest) -> Project:
        paths = self._get_paths(req.id)
        if paths.metadata_file.exists():
            raise ValueError(f"Project '{req.id}' already exists.")
        
        _ensure_directory(paths.root)
        _ensure_directory(paths.memory)
        _ensure_directory(paths.l2)
        _ensure_directory(paths.archive)
        _ensure_directory(paths.vectors)
        _ensure_directory(paths.vector_store)

        proj = Project(id=req.id, name=req.name, description=req.description, scope=ProjectScope.PRIVATE)
        paths.metadata_file.write_text(proj.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"Created project: {req.id}")
        return proj
