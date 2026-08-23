"""LanceDB Vector Store (Dual-Write)."""

from __future__ import annotations

from pathlib import Path
from loguru import logger
from ..models import MemoryEntry
from .embeddings import Embedder

class VectorStore:
    def __init__(self, uri: Path, embedder: Embedder, enabled: bool):
        self.uri = uri
        self.embedder = embedder
        self.enabled = enabled
        self._db = None
        self._table = None

    def _init_db(self):
        if not self.enabled: return
        if self._db is None:
            import lancedb
            import pyarrow as pa
            
            self.uri.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(self.uri))
            
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("project_id", pa.string()),
                pa.field("text", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), self.embedder.dimension()))
            ])
            
            try:
                self._table = self._db.open_table("memories")
            except Exception:
                self._table = self._db.create_table("memories", schema=schema)
            logger.debug(f"Initialized LanceDB vector store at {self.uri}")

    def add(self, entry: MemoryEntry) -> None:
        if not self.enabled: return
        self._init_db()
        text = f"{entry.metadata.get('title', '')}\n\n{entry.content}"
        vector = self.embedder.embed([text])[0]
        
        data = [{"id": str(entry.id), "project_id": entry.project_id, "text": text, "vector": vector}]
        self._table.add(data)

    def delete(self, memory_id: str) -> None:
        if not self.enabled: return
        self._init_db()
        self._table.delete(f"id = '{memory_id}'")

    def search(self, project_id: str, query: str, top_k: int) -> list[dict]:
        if not self.enabled: return []
        self._init_db()
        vector = self.embedder.embed([query])[0]
        results = self._table.search(vector).where(f"project_id = '{project_id}'").limit(top_k).to_list()
        return results
