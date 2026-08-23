"""Tool execution context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import AppConfig
from ..models import ProjectPaths
from ..workspace import get_project_paths


@dataclass
class ToolContext:
    project_id: str
    config: AppConfig
    project_paths: ProjectPaths
    project_service: Any
    memory_service: Any
    state_manager: Any


def build_tool_context(
    project_id: str,
    config: AppConfig,
    workspace_root: Path,
    project_service: Any,
    memory_service: Any,
    state_manager: Any,
) -> ToolContext:
    paths = get_project_paths(workspace_root, project_id, config)
    return ToolContext(
        project_id=project_id,
        config=config,
        project_paths=paths,
        project_service=project_service,
        memory_service=memory_service,
        state_manager=state_manager,
    )
