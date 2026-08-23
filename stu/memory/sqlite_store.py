"""L3 SQLite WAL Archive."""

from __future__ import annotations

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from loguru import logger

from ..models import MemoryEntry
from ..constants import MemoryLayer

class SqliteStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id)")
            conn.commit()
        logger.debug(f"Initialized SQLite WAL archive at {self.db_path}")

    def insert(self, entry: MemoryEntry) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO memories (id, project_id, key, title, content, tags, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(entry.id), entry.project_id, entry.key, 
                entry.metadata.get("title", ""), entry.content,
                json.dumps(entry.metadata.get("tags", [])),
                entry.created_at.isoformat(), json.dumps(entry.metadata)
            ))
            conn.commit()

    def get(self, memory_id: str) -> MemoryEntry | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if not row: return None
            return self._row_to_entry(row)

    def list(self, project_id: str, query: str | None = None, limit: int = 50, offset: int = 0) -> list[MemoryEntry]:
        with self._connect() as conn:
            if query:
                like = f"%{query}%"
                rows = conn.execute("""
                    SELECT * FROM memories WHERE project_id = ? AND (title LIKE ? OR content LIKE ?)
                    ORDER BY created_at DESC LIMIT ? OFFSET ?
                """, (project_id, like, like, limit, offset)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM memories WHERE project_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?
                """, (project_id, limit, offset)).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def delete(self, memory_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        meta = json.loads(row["metadata"])
        meta["title"] = row["title"]
        meta["tags"] = json.loads(row["tags"])
        return MemoryEntry(
            id=row["id"], 
            project_id=row["project_id"], 
            layer=MemoryLayer.L2,
            key=row["key"],
            content=row["content"], 
            created_at=datetime.fromisoformat(row["created_at"]), 
            metadata=meta
        )
