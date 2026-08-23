"""Workspace bootstrap and strict sandbox enforcement."""

from __future__ import annotations

import re
from pathlib import Path
from loguru import logger
from .config import AppConfig
from .constants import LoopPhase, LoopStatus
from .models import LoopState, WorkspaceManifest, ProjectPaths

PROJECT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$", re.IGNORECASE)

def _validate_project_id(project_id: str) -> None:
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ValueError("Invalid project_id. Use 1-64 chars: letters, numbers, '.', '_', '-'.")

def _resolve_inside_root(root: Path, candidate: str, fail_on_escape: bool) -> Path:
    root_resolved = root.resolve()
    candidate_path = Path(candidate).expanduser()
    if not candidate_path.is_absolute(): candidate_path = root_resolved / candidate_path
    candidate_resolved = candidate_path.resolve()
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        message = f"Path {candidate_resolved} escapes workspace root {root_resolved}."
        if fail_on_escape: raise ValueError(message) from exc
        logger.warning(message + " Continuing because fail_on_symlink_escape is false.")
    return candidate_resolved

def _ensure_directory(path: Path) -> None:
    if path.exists() and not path.is_dir(): raise ValueError(f"Expected directory but found file: {path}")
    path.mkdir(parents=True, exist_ok=True)

def get_project_paths(root: Path, project_id: str, config: AppConfig) -> ProjectPaths:
    _validate_project_id(project_id)
    fail = config.workspace.fail_on_symlink_escape
    proj_root = _resolve_inside_root(root, f"{config.workspace.projects_dir}/{project_id}", fail)
    
    mem_root = _resolve_inside_root(proj_root, config.memory.project_memory_dir, fail)
    l2 = _resolve_inside_root(mem_root, config.memory.project_l2_dir, fail)
    archive = _resolve_inside_root(mem_root, config.memory.project_archive_dir, fail)
    vectors = _resolve_inside_root(mem_root, config.memory.project_vectors_dir, fail)
    vector_store = _resolve_inside_root(vectors, "lancedb", fail)
    
    sqlite_db = _resolve_inside_root(archive, config.memory.sqlite_filename, fail)
    metadata_file = _resolve_inside_root(proj_root, "project.json", fail)

    return ProjectPaths(
        root=proj_root, memory=mem_root, l2=l2, archive=archive, 
        vectors=vectors, vector_store=vector_store, sqlite_db=sqlite_db, metadata_file=metadata_file
    )

def bootstrap_workspace(config: AppConfig) -> WorkspaceManifest:
    fail = config.workspace.fail_on_symlink_escape
    root = Path(config.workspace.root).expanduser()
    if not root.is_absolute(): root = Path.cwd() / root
    root = root.resolve()
    _ensure_directory(root)

    paths = {
        "projects": config.workspace.projects_dir, "models": config.workspace.models_dir,
        "logs": config.workspace.logs_dir, "runtime": config.workspace.runtime_dir,
        "tmp": config.workspace.tmp_dir, "artifacts": config.workspace.artifacts_dir,
        "mcp": config.workspace.mcp_dir
    }
    resolved = {k: _resolve_inside_root(root, v, fail) for k, v in paths.items()}
    for p in resolved.values(): _ensure_directory(p)

    default_paths = get_project_paths(root, config.app.default_project_id, config)
    for p in [default_paths.root, default_paths.memory, default_paths.l2, default_paths.archive, default_paths.vectors, default_paths.vector_store]:
        _ensure_directory(p)

    if not default_paths.metadata_file.exists():
        from .models import Project
        from .constants import ProjectScope
        proj = Project(id=config.app.default_project_id, name=config.app.default_project_id, scope=ProjectScope.PRIVATE)
        default_paths.metadata_file.write_text(proj.model_dump_json(indent=2), encoding="utf-8")

    loop_state_file = _resolve_inside_root(resolved["runtime"], config.execution.loop_state_filename, fail)
    if not loop_state_file.exists():
        initial_state = LoopState(status=LoopStatus.IDLE, phase=LoopPhase.IDLE, project_id=config.app.default_project_id)
        loop_state_file.write_text(initial_state.model_dump_json(indent=2), encoding="utf-8")

    return WorkspaceManifest(
        root=root, projects=resolved["projects"], default_project=default_paths.root,
        memory=default_paths.memory, memory_l2=default_paths.l2, archive=default_paths.archive,
        vectors=default_paths.vectors, vector_store=default_paths.vector_store, models=resolved["models"],
        logs=resolved["logs"], runtime=resolved["runtime"], tmp=resolved["tmp"],
        artifacts=resolved["artifacts"], mcp=resolved["mcp"], loop_state_file=loop_state_file
    )
