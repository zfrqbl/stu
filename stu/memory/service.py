"""Memory orchestrator service."""

from __future__ import annotations

from uuid import uuid4
from datetime import datetime, timezone
from loguru import logger

from ..config import AppConfig
from ..constants import MemoryLayer
from ..models import MemoryEntry, MemoryCreateRequest, MemoryReadResponse, MemorySearchResult, ProjectPaths
from ..workspace import get_project_paths
from .scratchpad import ScratchpadStore
from .sqlite_store import SqliteStore
from .markdown_store import MarkdownStore
from .vector_store import VectorStore
from .embeddings import get_embedder

class MemoryService:
    def __init__(self, workspace_root, config: AppConfig, models_dir):
        self.workspace_root = workspace_root
        self.config = config
        self.scratchpad = ScratchpadStore(config.memory.l1_max_entries)
        self.embedder = get_embedder(config.memory.embedding, config.memory.rag.enabled, models_dir)

    def _get_stores(self, project_id: str) -> tuple[ProjectPaths, SqliteStore, MarkdownStore, VectorStore]:
        paths = get_project_paths(self.workspace_root, project_id, self.config)
        sqlite = SqliteStore(paths.sqlite_db)
        sqlite.initialize()
        markdown = MarkdownStore(paths.l2)
        vector = VectorStore(paths.vector_store, self.embedder, self.config.memory.rag.enabled)
        return paths, sqlite, markdown, vector

    def create_memory(self, project_id: str, req: MemoryCreateRequest) -> MemoryReadResponse:
        paths, sqlite, markdown, vector = self._get_stores(project_id)
        
        entry = MemoryEntry(
            id=uuid4(), 
            project_id=project_id, 
            layer=MemoryLayer.L2,
            key=req.title.lower().replace(" ", "_"),
            content=req.content, 
            created_at=datetime.now(timezone.utc),
            metadata={"title": req.title, "tags": req.tags}
        )

        # 1. L3 SQLite (Source of Truth)
        sqlite.insert(entry)
        
        # 2. L2 Markdown (Human Readable)
        try:
            markdown.write(entry)
        except Exception as e:
            logger.error(f"Failed to write L2 Markdown for {entry.id}: {e}")
            sqlite.delete(str(entry.id))
            raise ValueError("Failed to persist memory to Markdown filing cabinet.")

        # 3. Vector Store (Dual-Write)
        try:
            vector.add(entry)
        except Exception as e:
            logger.warning(f"Failed to write vector for {entry.id}: {e}")

        # 4. L1 Scratchpad
        self.scratchpad.set(project_id, str(entry.id), entry.content)

        return self._to_response(entry)

    def get_memory(self, project_id: str, memory_id: str) -> MemoryReadResponse | None:
        _, sqlite, _, _ = self._get_stores(project_id)
        entry = sqlite.get(memory_id)
        if not entry or entry.project_id != project_id: return None
        return self._to_response(entry)

    def list_memories(self, project_id: str, query: str | None = None) -> list[MemoryReadResponse]:
        _, sqlite, _, _ = self._get_stores(project_id)
        entries = sqlite.list(project_id, query)
        return [self._to_response(e) for e in entries]

    def delete_memory(self, project_id: str, memory_id: str) -> bool:
        _, sqlite, markdown, vector = self._get_stores(project_id)
        entry = sqlite.get(memory_id)
        if not entry or entry.project_id != project_id: return False

        sqlite.delete(memory_id)
        markdown.delete(entry)
        vector.delete(memory_id)
        self.scratchpad.delete(project_id, memory_id)
        return True

    def search_memory(self, project_id: str, query: str) -> list[MemorySearchResult]:
        _, _, _, vector = self._get_stores(project_id)
        if not self.config.memory.rag.enabled:
            # Fallback to SQLite keyword search if RAG is disabled
            entries = self.list_memories(project_id, query)
            return [MemorySearchResult(memory=e, score=1.0) for e in entries]
            
        results = vector.search(project_id, query, self.config.memory.rag.top_k)
        out = []
        for r in results:
            entry = self.get_memory(project_id, r["id"])
            if entry:
                out.append(MemorySearchResult(memory=entry, score=1.0 - r.get("_distance", 0.0)))
        return out

    def _to_response(self, entry: MemoryEntry) -> MemoryReadResponse:
        return MemoryReadResponse(
            id=str(entry.id), project_id=entry.project_id,
            title=entry.metadata.get("title", ""), content=entry.content,
            tags=entry.metadata.get("tags", []), created_at=entry.created_at
        )
