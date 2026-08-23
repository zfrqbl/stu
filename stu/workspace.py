"""Workspace bootstrap and strict sandbox enforcement."""

from __future__ import annotations

import re
from pathlib import Path

from loguru import logger

from .config import AppConfig
from .constants import LoopPhase, LoopStatus
from .models import LoopState, WorkspaceManifest

PROJECT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$", re.IGNORECASE)


def _validate_project_id(project_id: str) -> None:
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ValueError(
            "Invalid project_id. Use 1-64 characters: letters, numbers, '.', '_', '-'."
        )


def _resolve_inside_root(root: Path, candidate: str, fail_on_escape: bool) -> Path:
    root_resolved = root.resolve()
    candidate_path = Path(candidate).expanduser()

    if not candidate_path.is_absolute():
        candidate_path = root_resolved / candidate_path

    candidate_resolved = candidate_path.resolve()

    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        message = f"Path {candidate_resolved} escapes workspace root {root_resolved}."
        if fail_on_escape:
            raise ValueError(message) from exc
        logger.warning(message + " Continuing because fail_on_symlink_escape is false.")

    return candidate_resolved


def _ensure_directory(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError(f"Expected directory but found file: {path}")
    path.mkdir(parents=True, exist_ok=True)


def bootstrap_workspace(config: AppConfig) -> WorkspaceManifest:
    fail_on_escape = config.workspace.fail_on_symlink_escape

    root = Path(config.workspace.root).expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    root = root.resolve()

    _ensure_directory(root)
    logger.debug(f"Workspace root resolved: {root}")

    projects = _resolve_inside_root(root, config.workspace.projects_dir, fail_on_escape)
    memory = _resolve_inside_root(root, config.workspace.memory_dir, fail_on_escape)
    archive = _resolve_inside_root(root, config.workspace.archive_dir, fail_on_escape)
    vectors = _resolve_inside_root(root, config.workspace.vectors_dir, fail_on_escape)
    models = _resolve_inside_root(root, config.workspace.models_dir, fail_on_escape)
    logs = _resolve_inside_root(root, config.workspace.logs_dir, fail_on_escape)
    runtime = _resolve_inside_root(root, config.workspace.runtime_dir, fail_on_escape)
    tmp = _resolve_inside_root(root, config.workspace.tmp_dir, fail_on_escape)
    artifacts = _resolve_inside_root(root, config.workspace.artifacts_dir, fail_on_escape)
    mcp = _resolve_inside_root(root, config.workspace.mcp_dir, fail_on_escape)

    _ensure_directory(projects)
    _ensure_directory(memory)
    _ensure_directory(archive)
    _ensure_directory(vectors)
    _ensure_directory(models)
    _ensure_directory(logs)
    _ensure_directory(runtime)
    _ensure_directory(tmp)
    _ensure_directory(artifacts)
    _ensure_directory(mcp)

    memory_l2 = _resolve_inside_root(memory, config.memory.l2_subdir, fail_on_escape)
    vector_store = _resolve_inside_root(vectors, config.memory.vector_store_subdir, fail_on_escape)

    _ensure_directory(memory_l2)
    _ensure_directory(vector_store)

    _validate_project_id(config.app.default_project_id)
    default_project = _resolve_inside_root(projects, config.app.default_project_id, fail_on_escape)
    _ensure_directory(default_project)

    loop_state_file = _resolve_inside_root(runtime, config.execution.loop_state_filename, fail_on_escape)

    if loop_state_file.exists():
        if loop_state_file.is_dir():
            raise ValueError(f"Loop state path is a directory: {loop_state_file}")

        try:
            LoopState.model_validate_json(loop_state_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"Existing loop state file is invalid: {loop_state_file}") from exc
    else:
        initial_state = LoopState(
            status=LoopStatus.IDLE,
            phase=LoopPhase.IDLE,
            project_id=config.app.default_project_id,
            iteration=0,
            message="Initial loop state created by workspace bootstrap.",
        )
        loop_state_file.write_text(initial_state.model_dump_json(indent=2), encoding="utf-8")
        logger.debug(f"Initial loop state written: {loop_state_file}")

    manifest = WorkspaceManifest(
        root=root,
        projects=projects,
        default_project=default_project,
        memory=memory,
        memory_l2=memory_l2,
        archive=archive,
        vectors=vectors,
        vector_store=vector_store,
        models=models,
        logs=logs,
        runtime=runtime,
        tmp=tmp,
        artifacts=artifacts,
        mcp=mcp,
        loop_state_file=loop_state_file,
    )

    logger.info("Workspace bootstrap complete.")
    return manifest
