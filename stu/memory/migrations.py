"""SQLite schema migration support for memory lifecycle."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger

CURRENT_SCHEMA_VERSION = 2

MIGRATIONS = {
    1: [
        """
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
        """,
        "CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id)",
    ],
    2: [
        "ALTER TABLE memories ADD COLUMN importance_score REAL DEFAULT 0.5",
        "ALTER TABLE memories ADD COLUMN access_count INTEGER DEFAULT 0",
        "ALTER TABLE memories ADD COLUMN last_accessed_at TEXT",
        "ALTER TABLE memories ADD COLUMN created_by TEXT DEFAULT 'user'",
        "ALTER TABLE memories ADD COLUMN memory_type TEXT DEFAULT 'episodic'",
        "ALTER TABLE memories ADD COLUMN expiry_at TEXT",
        "ALTER TABLE memories ADD COLUMN status TEXT DEFAULT 'active'",
        "ALTER TABLE memories ADD COLUMN consolidated_into TEXT",
        "ALTER TABLE memories ADD COLUMN composite_score REAL DEFAULT 0.5",
    ],
}


def get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        cursor = conn.execute("SELECT MAX(version) FROM schema_migrations")
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


def apply_migrations(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

        current_version = get_schema_version(conn)

        if current_version >= CURRENT_SCHEMA_VERSION:
            return

        for version in range(current_version + 1, CURRENT_SCHEMA_VERSION + 1):
            migrations = MIGRATIONS.get(version, [])
            for sql in migrations:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError as e:
                    if "duplicate column" not in str(e).lower():
                        raise
                    logger.debug(f"Column already exists, skipping: {sql[:60]}")

            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
            conn.commit()
            logger.info(f"Applied memory schema migration v{version} to {db_path.name}")

    finally:
        conn.close()
