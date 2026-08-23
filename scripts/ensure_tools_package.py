#!/usr/bin/env python3
"""Create Milestone 5 tooling files if they are missing or incomplete."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES: dict[str, str] = {}

FILES["stu/tools/__init__.py"] = '''"""Tooling subsystem for Project Stu v3.0."""
'''

FILES["stu/tools/context.py"] = '''"""Tool execution context."""

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
'''

FILES["stu/tools/args.py"] = '''"""Typed argument models for native tools."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MemoryCreateArgs(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)


class MemorySearchArgs(BaseModel):
    query: str | None = None
    limit: int = Field(20, ge=1, le=100)


class MemoryGetArgs(BaseModel):
    memory_id: str


class ProjectGetArgs(BaseModel):
    pass


class WorkspaceListArgs(BaseModel):
    path: str = ""


class WorkspaceReadArgs(BaseModel):
    path: str


class WorkspaceWriteArgs(BaseModel):
    path: str
    content: str


class SystemStatusArgs(BaseModel):
    pass
'''

FILES["stu/tools/native.py"] = '''"""Native tool implementations."""

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
'''

FILES["stu/tools/catalog.py"] = '''"""Universal Tool Catalog."""

from __future__ import annotations

from ..config import ToolsConfig
from ..constants import ToolKind
from ..models import ToolDescriptor
from .native import NATIVE_TOOL_IMPLS


class ToolCatalog:
    def __init__(self, config: ToolsConfig):
        self.config = config
        self._entries = {entry.name: entry for entry in config.catalog}
        self._implementations = {}
        self._arg_models = {}

        self._register_native_tools()
        self._validate()

    def _register_native_tools(self) -> None:
        for name, (impl, arg_model) in NATIVE_TOOL_IMPLS.items():
            self._implementations[name] = impl
            self._arg_models[name] = arg_model

    def _validate(self) -> None:
        for name in self._entries:
            if name not in self._implementations:
                raise ValueError(f"Catalog tool '{name}' has no registered implementation.")

    @property
    def core_fallback_names(self) -> list[str]:
        return list(self.config.core_fallback)

    def list_tools(self, include_disabled: bool = True) -> list[ToolDescriptor]:
        descriptors: list[ToolDescriptor] = []

        for name, entry in self._entries.items():
            enabled = self.config.enabled and entry.enabled

            if not include_disabled and not enabled:
                continue

            arg_model = self._arg_models.get(name)
            input_schema = arg_model.model_json_schema() if arg_model else {}

            descriptors.append(
                ToolDescriptor(
                    name=name,
                    kind=ToolKind.NATIVE,
                    safety_level=entry.safety_level,
                    description=entry.description,
                    input_schema=input_schema,
                    enabled=enabled,
                )
            )

        return descriptors

    def get_descriptor(self, name: str) -> ToolDescriptor | None:
        entry = self._entries.get(name)
        if not entry:
            return None

        arg_model = self._arg_models.get(name)
        input_schema = arg_model.model_json_schema() if arg_model else {}

        return ToolDescriptor(
            name=name,
            kind=ToolKind.NATIVE,
            safety_level=entry.safety_level,
            description=entry.description,
            input_schema=input_schema,
            enabled=self.config.enabled and entry.enabled,
        )

    def get_enabled_descriptor(self, name: str) -> ToolDescriptor | None:
        descriptor = self.get_descriptor(name)
        if not descriptor or not descriptor.enabled:
            return None
        return descriptor

    def get_implementation(self, name: str):
        return self._implementations.get(name)

    def get_arg_model(self, name: str):
        return self._arg_models.get(name)
'''

FILES["stu/tools/rag.py"] = '''"""Semantic Tool RAG with deterministic core fallback."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from ..config import EmbeddingConfig, ToolsConfig
from ..models import ToolDescriptor
from .catalog import ToolCatalog


class ToolRagService:
    def __init__(
        self,
        catalog: ToolCatalog,
        tools_config: ToolsConfig,
        embedding_config: EmbeddingConfig,
        models_dir: Path,
    ):
        self.catalog = catalog
        self.tools_config = tools_config
        self.embedding_config = embedding_config
        self.models_dir = models_dir

        self.enabled = tools_config.rag.enabled
        self.top_k = tools_config.rag.top_k
        self.uri = models_dir / tools_config.rag.vector_subdir / "lancedb"

        self._embedder = None
        self._db = None
        self._table = None
        self._ready = False
        self._failed = False

    def prepare(self) -> None:
        if not self.enabled or self._ready or self._failed:
            return

        try:
            from ..memory.embeddings import get_embedder

            self._embedder = get_embedder(self.embedding_config, True, self.models_dir)

            descriptors = self.catalog.list_tools(include_disabled=False)
            if not descriptors:
                self._ready = True
                return

            texts = [f"{d.name}: {d.description}" for d in descriptors]
            vectors = self._embedder.embed(texts)

            import lancedb

            self.uri.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(self.uri))

            data = []
            for descriptor, text, vector in zip(descriptors, texts, vectors):
                data.append(
                    {
                        "name": descriptor.name,
                        "text": text,
                        "vector": vector,
                    }
                )

            self._table = self._db.create_table("tools", data=data, mode="overwrite")
            self._ready = True
            logger.info("Tool RAG index prepared.")
        except Exception as exc:
            logger.warning(f"Tool RAG initialization failed; using core fallback. {exc}")
            self._failed = True
            self.enabled = False

    def select_tools(self, query: str) -> list[ToolDescriptor]:
        if not query.strip():
            return self._fallback()

        self.prepare()

        if not self.enabled or not self._ready or self._table is None or self._embedder is None:
            return self._fallback()

        try:
            vector = self._embedder.embed([query])[0]
            rows = self._table.search(vector).limit(self.top_k).to_list()

            selected: list[ToolDescriptor] = []
            for row in rows:
                descriptor = self.catalog.get_enabled_descriptor(row.get("name", ""))
                if descriptor:
                    selected.append(descriptor)

            if selected:
                return selected[: self.top_k]
        except Exception as exc:
            logger.warning(f"Tool RAG search failed; using core fallback. {exc}")

        return self._fallback()

    def _fallback(self) -> list[ToolDescriptor]:
        descriptors: list[ToolDescriptor] = []

        for name in self.catalog.core_fallback_names:
            descriptor = self.catalog.get_enabled_descriptor(name)
            if descriptor:
                descriptors.append(descriptor)

        if not descriptors:
            descriptors = self.catalog.list_tools(include_disabled=False)

        return descriptors[: self.top_k]
'''

FILES["stu/tools/executor.py"] = '''"""Tool Executor with timeout, validation, and output limits."""

from __future__ import annotations

import asyncio
import json
import time

from pydantic import ValidationError

from ..config import ToolsConfig
from ..constants import ToolExecutionStatus
from ..models import ToolInvokeResponse
from .catalog import ToolCatalog
from .context import ToolContext


class ToolExecutor:
    def __init__(self, catalog: ToolCatalog, config: ToolsConfig):
        self.catalog = catalog
        self.config = config

    async def invoke(
        self,
        tool_name: str,
        arguments: dict,
        context: ToolContext,
    ) -> ToolInvokeResponse:
        start = time.perf_counter()

        if not self.config.enabled:
            return self._response(
                tool_name,
                ToolExecutionStatus.BLOCKED,
                start,
                error="Tool execution is disabled.",
            )

        descriptor = self.catalog.get_enabled_descriptor(tool_name)
        if not descriptor:
            return self._response(
                tool_name,
                ToolExecutionStatus.BLOCKED,
                start,
                error="Tool not found or disabled.",
            )

        impl = self.catalog.get_implementation(tool_name)
        arg_model = self.catalog.get_arg_model(tool_name)

        if not impl or not arg_model:
            return self._response(
                tool_name,
                ToolExecutionStatus.ERROR,
                start,
                error="Tool implementation is incomplete.",
            )

        try:
            parsed_args = arg_model.model_validate(arguments)
        except ValidationError as exc:
            return self._response(
                tool_name,
                ToolExecutionStatus.ERROR,
                start,
                error=str(exc),
            )

        try:
            raw_output = await asyncio.wait_for(
                asyncio.to_thread(impl, parsed_args, context),
                timeout=self.config.default_timeout_seconds,
            )
        except asyncio.TimeoutError:
            return self._response(
                tool_name,
                ToolExecutionStatus.TIMEOUT,
                start,
                error="Tool execution timed out.",
            )
        except Exception as exc:
            return self._response(
                tool_name,
                ToolExecutionStatus.ERROR,
                start,
                error=str(exc),
            )

        output = self._truncate(raw_output)

        return self._response(
            tool_name,
            ToolExecutionStatus.SUCCESS,
            start,
            output=output,
        )

    def _response(
        self,
        tool_name: str,
        status: ToolExecutionStatus,
        start: float,
        output=None,
        error: str | None = None,
    ) -> ToolInvokeResponse:
        duration_ms = (time.perf_counter() - start) * 1000.0
        return ToolInvokeResponse(
            tool_name=tool_name,
            status=status,
            output=output,
            error=error,
            duration_ms=duration_ms,
        )

    def _truncate(self, output):
        max_bytes = self.config.max_output_bytes

        try:
            serialized = json.dumps(output, ensure_ascii=False, default=str)
        except Exception:
            serialized = str(output)

        encoded = serialized.encode("utf-8")
        if len(encoded) <= max_bytes:
            return output

        preview = encoded[:max_bytes].decode("utf-8", errors="replace")
        return {
            "truncated": True,
            "preview": preview,
        }
'''

FILES["stu/api/tools.py"] = '''"""Tools API router."""

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
'''


def main() -> int:
    for relative_path, content in FILES.items():
        path = ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path}")

    print("Tools package ensured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
