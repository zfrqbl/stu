"""Memory orchestrator service with lifecycle support."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from loguru import logger

from ..config import AppConfig
from ..models import MemoryCreateRequest, MemoryEntry, MemoryReadResponse, MemorySearchResult
from ..constants import MemoryLayer
from .sqlite_store import SqliteStore
from .markdown_store import MarkdownStore
from .vector_store import VectorStore
from .embeddings import get_embedder


class MemoryService:
    def __init__(self, workspace_root, config: AppConfig, models_dir):
        self.workspace_root = workspace_root
        self.config = config
        self.models_dir = models_dir
        self._stores: dict[str, SqliteStore] = {}
        self._markdown_stores: dict[str, MarkdownStore] = {}

    def _get_sqlite_store(self, project_id: str) -> SqliteStore:
        if project_id not in self._stores:
            from ..workspace import get_project_paths
            paths = get_project_paths(self.workspace_root, project_id, self.config)
            self._stores[project_id] = SqliteStore(paths.sqlite_db)
        return self._stores[project_id]

    def _get_markdown_store(self, project_id: str) -> MarkdownStore:
        if project_id not in self._markdown_stores:
            from ..workspace import get_project_paths
            paths = get_project_paths(self.workspace_root, project_id, self.config)
            self._markdown_stores[project_id] = MarkdownStore(paths.l2)
        return self._markdown_stores[project_id]

    def create_memory(self, project_id: str, req: MemoryCreateRequest) -> MemoryReadResponse:
        now = datetime.now(timezone.utc)
        entry = MemoryEntry(
            id=uuid4(),
            project_id=project_id,
            layer=MemoryLayer.L3,
            key=req.title.lower().replace(" ", "_"),
            content=req.content,
            created_at=now,
            metadata={
                "title": req.title,
                "tags": req.tags,
                "importance_score": 0.5,
                "access_count": 0,
                "last_accessed_at": now.isoformat(),
                "created_by": "user",
                "memory_type": "episodic",
                "status": "active",
                "composite_score": 0.5,
            },
        )

        store = self._get_sqlite_store(project_id)
        store.insert(entry)

        try:
            md_store = self._get_markdown_store(project_id)
            md_store.write(entry)
        except Exception as e:
            logger.warning(f"Failed to write markdown for memory {entry.id}: {e}")

        return self._to_response(entry)

    def create_memory_from_dict(self, project_id: str, data: dict) -> MemoryReadResponse:
        now = datetime.now(timezone.utc)
        entry = MemoryEntry(
            id=uuid4(),
            project_id=project_id,
            layer=MemoryLayer.L3,
            key=data.get("title", "untitled").lower().replace(" ", "_"),
            content=data.get("content", ""),
            created_at=now,
            metadata={
                "title": data.get("title", "Untitled"),
                "tags": data.get("tags", []),
                "importance_score": data.get("importance_score", 0.5),
                "access_count": 0,
                "last_accessed_at": now.isoformat(),
                "created_by": data.get("created_by", "agent"),
                "memory_type": data.get("memory_type", "episodic"),
                "status": "active",
                "composite_score": data.get("importance_score", 0.5),
            },
        )

        store = self._get_sqlite_store(project_id)
        store.insert(entry)

        return self._to_response(entry)

    def get_memory(self, project_id: str, memory_id: str) -> MemoryReadResponse | None:
        store = self._get_sqlite_store(project_id)
        entry = store.get(memory_id)
        if not entry:
            return None

        store.update_access(memory_id)
        return self._to_response(entry)

    def list_memories(
        self,
        project_id: str,
        query: str | None = None,
        status_filter: str | None = "active",
    ) -> list[MemoryReadResponse]:
        store = self._get_sqlite_store(project_id)
        entries = store.list(project_id, query=query, status_filter=status_filter)
        return [self._to_response(e) for e in entries]

    def search_memory(self, project_id: str, query: str) -> list[MemorySearchResult]:
        store = self._get_sqlite_store(project_id)
        entries = store.list(project_id, query=query, limit=10)
        return [
            MemorySearchResult(memory=self._to_response(e), score=e.metadata.get("composite_score"))
            for e in entries
        ]

    def archive_memory(self, project_id: str, memory_id: str) -> bool:
        store = self._get_sqlite_store(project_id)
        entry = store.get(memory_id)
        if not entry:
            return False
        store.update_status(memory_id, "archived")
        return True

    def restore_memory(self, project_id: str, memory_id: str) -> bool:
        store = self._get_sqlite_store(project_id)
        entry = store.get(memory_id)
        if not entry:
            return False
        store.update_status(memory_id, "active")
        return True

    def delete_memory(self, project_id: str, memory_id: str) -> bool:
        """Alias for hard_delete_memory to support the standard API router."""
        store = self._get_sqlite_store(project_id)
        return store.delete(memory_id)
    def prune_memory(self, project_id: str, memory_id: str) -> bool:
        store = self._get_sqlite_store(project_id)
        entry = store.get(memory_id)
        if not entry:
            return False
        store.update_status(memory_id, "pruned")
        return True

    def hard_delete_memory(self, project_id: str, memory_id: str) -> bool:
        store = self._get_sqlite_store(project_id)
        return store.delete(memory_id)

    def mark_consolidated(self, project_id: str, memory_id: str, consolidated_into: str = "") -> bool:
        store = self._get_sqlite_store(project_id)
        entry = store.get(memory_id)
        if not entry:
            return False
        store.mark_consolidated(memory_id, consolidated_into)
        return True

    def boost_memory(self, project_id: str, memory_id: str, amount: float = 0.2) -> bool:
        store = self._get_sqlite_store(project_id)
        entry = store.get(memory_id)
        if not entry:
            return False
        current = entry.metadata.get("importance_score", 0.5)
        new_score = min(1.0, current + amount)
        store.update_composite_score(memory_id, new_score)
        return True

    def get_lifecycle_stats(self, project_id: str) -> dict[str, int]:
        store = self._get_sqlite_store(project_id)
        return store.count_by_status(project_id)

    def _to_response(self, entry: MemoryEntry) -> MemoryReadResponse:
        return MemoryReadResponse(
            id=str(entry.id),
            project_id=entry.project_id,
            title=entry.metadata.get("title", ""),
            content=entry.content,
            tags=entry.metadata.get("tags", []),
            created_at=entry.created_at,
        )
