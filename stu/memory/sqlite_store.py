"""L3 SQLite WAL Archive with lifecycle support."""

from __future__ import annotations

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger

from ..models import MemoryEntry
from ..constants import MemoryLayer
from .migrations import apply_migrations


class SqliteStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        apply_migrations(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def insert(self, entry: MemoryEntry) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memories
                (id, project_id, key, title, content, tags, created_at, metadata,
                 importance_score, access_count, last_accessed_at, created_by,
                 memory_type, expiry_at, status, consolidated_into, composite_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(entry.id),
                entry.project_id,
                entry.key,
                entry.metadata.get("title", ""),
                entry.content,
                json.dumps(entry.metadata.get("tags", [])),
                entry.created_at.isoformat(),
                json.dumps(entry.metadata),
                entry.metadata.get("importance_score", 0.5),
                entry.metadata.get("access_count", 0),
                entry.metadata.get("last_accessed_at"),
                entry.metadata.get("created_by", "user"),
                entry.metadata.get("memory_type", "episodic"),
                entry.metadata.get("expiry_at"),
                entry.metadata.get("status", "active"),
                entry.metadata.get("consolidated_into"),
                entry.metadata.get("composite_score", 0.5),
            ))
            conn.commit()

    def get(self, memory_id: str) -> MemoryEntry | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if not row:
                return None
            return self._row_to_entry(row)

    def list(
        self,
        project_id: str,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
        status_filter: str | None = "active",
    ) -> list[MemoryEntry]:
        with self._connect() as conn:
            base_where = "project_id = ?"
            params: list = [project_id]

            if status_filter:
                base_where += " AND status = ?"
                params.append(status_filter)

            if query:
                like = f"%{query}%"
                base_where += " AND (title LIKE ? OR content LIKE ?)"
                params.extend([like, like])

            sql = f"""
                SELECT * FROM memories
                WHERE {base_where}
                ORDER BY composite_score DESC, created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])

            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def list_all_statuses(
        self,
        project_id: str,
        limit: int = 200,
    ) -> list[MemoryEntry]:
        return self.list(project_id, limit=limit, status_filter=None)

    def update_access(self, memory_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("""
                UPDATE memories
                SET access_count = access_count + 1, last_accessed_at = ?
                WHERE id = ?
            """, (now, memory_id))
            conn.commit()

    def update_status(self, memory_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE memories SET status = ? WHERE id = ?",
                (status, memory_id),
            )
            conn.commit()

    def update_composite_score(self, memory_id: str, score: float) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE memories SET composite_score = ? WHERE id = ?",
                (score, memory_id),
            )
            conn.commit()

    def mark_consolidated(self, memory_id: str, consolidated_into: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE memories SET status = 'consolidated', consolidated_into = ? WHERE id = ?",
                (consolidated_into, memory_id),
            )
            conn.commit()

    def delete(self, memory_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0

    def count_by_status(self, project_id: str) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM memories WHERE project_id = ? GROUP BY status",
                (project_id,),
            ).fetchall()
            return {row["status"]: row["cnt"] for row in rows}

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        meta = json.loads(row["metadata"]) if row["metadata"] else {}
        meta["title"] = row["title"]
        meta["tags"] = json.loads(row["tags"]) if row["tags"] else []
        meta["importance_score"] = row["importance_score"]
        meta["access_count"] = row["access_count"]
        meta["last_accessed_at"] = row["last_accessed_at"]
        meta["created_by"] = row["created_by"]
        meta["memory_type"] = row["memory_type"]
        meta["expiry_at"] = row["expiry_at"]
        meta["status"] = row["status"]
        meta["consolidated_into"] = row["consolidated_into"]
        meta["composite_score"] = row["composite_score"]

        return MemoryEntry(
            id=row["id"],
            project_id=row["project_id"],
            layer=MemoryLayer.L3,
            key=row["key"],
            content=row["content"],
            created_at=row["created_at"],
            metadata=meta,
        )
