"""Native tool implementations."""

from __future__ import annotations

from pathlib import Path

from ..models import MemoryCreateRequest
from .args import (
    MemoryCreateArgs,
    MemoryGetArgs,
    MemorySearchArgs,
    ProjectGetArgs,
    SystemStatusArgs,
    WorkspaceListArgs,
    WorkspaceReadArgs,
    WorkspaceWriteArgs,
)
from .context import ToolContext


def _resolve_inside_project(root: Path, raw_path: str) -> tuple[Path, Path]:
    resolved_root = root.resolve()

    if raw_path in ("", "."):
        return resolved_root, resolved_root

    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError("Absolute paths are not allowed.")

    resolved_target = (resolved_root / candidate).resolve()

    try:
        resolved_target.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("Path escapes project sandbox.") from exc

    return resolved_root, resolved_target


def _resolve_inside_writable(root: Path, write_subdir: str, raw_path: str) -> tuple[Path, Path]:
    if Path(write_subdir).is_absolute():
        raise ValueError("Write subdirectory must be relative.")

    if not raw_path:
        raise ValueError("path is required.")

    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError("Absolute paths are not allowed.")

    resolved_root = root.resolve()
    writable_root = (resolved_root / write_subdir).resolve()

    try:
        writable_root.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("Write directory escapes project sandbox.") from exc

    resolved_target = (writable_root / candidate).resolve()

    try:
        resolved_target.relative_to(writable_root)
    except ValueError as exc:
        raise ValueError("Path escapes writable sandbox.") from exc

    return writable_root, resolved_target


def _assert_not_env(root: Path, target: Path) -> None:
    rel = target.relative_to(root)
    for part in rel.parts:
        if ".env" in part:
            raise ValueError("Access to environment files is blocked.")


def memory_create(args: MemoryCreateArgs, ctx: ToolContext):
    created = ctx.memory_service.create_memory(
        ctx.project_id,
        MemoryCreateRequest(title=args.title, content=args.content, tags=args.tags),
    )
    return created.model_dump(mode="json")


def memory_search(args: MemorySearchArgs, ctx: ToolContext):
    entries = ctx.memory_service.list_memories(ctx.project_id, query=args.query)
    entries = entries[: args.limit]
    return [entry.model_dump(mode="json") for entry in entries]


def memory_get(args: MemoryGetArgs, ctx: ToolContext):
    entry = ctx.memory_service.get_memory(ctx.project_id, args.memory_id)
    if not entry:
        raise ValueError("Memory not found.")
    return entry.model_dump(mode="json")


def project_get(args: ProjectGetArgs, ctx: ToolContext):
    project = ctx.project_service.get_project(ctx.project_id)
    if not project:
        raise ValueError("Project not found.")
    return project.model_dump(mode="json")


def workspace_list(args: WorkspaceListArgs, ctx: ToolContext):
    resolved_root, target = _resolve_inside_project(ctx.project_paths.root, args.path)

    if not target.exists():
        raise ValueError("Path does not exist.")
    if not target.is_dir():
        raise ValueError("Path is not a directory.")

    entries = []
    for p in sorted(target.iterdir()):
        rel = p.relative_to(resolved_root)
        entries.append(
            {
                "path": str(rel),
                "is_dir": p.is_dir(),
            }
        )
        if len(entries) >= 500:
            break

    relative_target = "" if target == resolved_root else str(target.relative_to(resolved_root))
    return {
        "path": relative_target,
        "entries": entries,
    }


def workspace_read(args: WorkspaceReadArgs, ctx: ToolContext):
    resolved_root, target = _resolve_inside_project(ctx.project_paths.root, args.path)

    if not target.exists() or not target.is_file():
        raise ValueError("File does not exist.")

    _assert_not_env(resolved_root, target)

    return target.read_text(encoding="utf-8", errors="replace")


def workspace_write(args: WorkspaceWriteArgs, ctx: ToolContext):
    writable_root, target = _resolve_inside_writable(
        ctx.project_paths.root,
        ctx.config.tools.write_subdir,
        args.path,
    )

    writable_root.mkdir(parents=True, exist_ok=True)

    if target.exists() and target.is_dir():
        raise ValueError("Target path is a directory.")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(args.content, encoding="utf-8")

    project_root = ctx.project_paths.root.resolve()
    rel = target.relative_to(project_root)

    return {
        "path": str(rel),
        "bytes_written": len(args.content.encode("utf-8")),
    }


def system_status(args: SystemStatusArgs, ctx: ToolContext):
    loop_state = None
    if ctx.state_manager is not None:
        state = ctx.state_manager.load_state()
        if state is not None:
            loop_state = state.model_dump(mode="json")

    return {
        "app": {
            "name": ctx.config.app.name,
            "version": ctx.config.app.version,
            "environment": ctx.config.app.environment.value,
        },
        "project_id": ctx.project_id,
        "tools_enabled": ctx.config.tools.enabled,
        "loop_state": loop_state,
    }


NATIVE_TOOL_IMPLS = {
    "memory_create": (memory_create, MemoryCreateArgs),
    "memory_search": (memory_search, MemorySearchArgs),
    "memory_get": (memory_get, MemoryGetArgs),
    "project_get": (project_get, ProjectGetArgs),
    "workspace_list": (workspace_list, WorkspaceListArgs),
    "workspace_read": (workspace_read, WorkspaceReadArgs),
    "workspace_write": (workspace_write, WorkspaceWriteArgs),
    "system_status": (system_status, SystemStatusArgs),
}
