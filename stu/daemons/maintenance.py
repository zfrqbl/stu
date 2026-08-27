"""MaintenanceDaemon: performs workspace cleanup and optimization."""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from loguru import logger

from .manager import Daemon


class MaintenanceDaemon(Daemon):
    """Maintains workspace health: WAL checkpoints, temp cleanup, L1 pruning."""

    def __init__(
        self,
        interval_seconds: float,
        enabled: bool,
        workspace_root: Path,
        projects_dir: Path,
        tmp_dir: Path,
        max_tmp_age_hours: float = 24.0,
    ):
        super().__init__("maintenance", interval_seconds, enabled)
        self.workspace_root = workspace_root
        self.projects_dir = projects_dir
        self.tmp_dir = tmp_dir
        self.max_tmp_age_hours = max_tmp_age_hours

    async def tick(self) -> None:
        self._checkpoint_sqlite_wal()
        self._cleanup_tmp_dir()
        self._verify_workspace_boundary()

    def _checkpoint_sqlite_wal(self) -> None:
        if not self.projects_dir.exists():
            return

        count = 0
        for project_dir in self.projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            archive_dir = project_dir / "memory" / "archive"
            if not archive_dir.exists():
                continue

            for db_file in archive_dir.glob("*.sqlite3"):
                try:
                    conn = sqlite3.connect(str(db_file))
                    conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
                    conn.close()
                    count += 1
                except Exception as e:
                    logger.warning(f"WAL checkpoint failed for {db_file}: {e}")

        if count > 0:
            logger.debug(f"MaintenanceDaemon: checkpointed {count} SQLite WAL files")

    def _cleanup_tmp_dir(self) -> None:
        if not self.tmp_dir.exists():
            return

        cutoff = time.time() - (self.max_tmp_age_hours * 3600)
        removed = 0

        for item in self.tmp_dir.iterdir():
            try:
                if item.is_file():
                    mtime = item.stat().st_mtime
                    if mtime < cutoff:
                        item.unlink()
                        removed += 1
                elif item.is_dir():
                    mtime = item.stat().st_mtime
                    if mtime < cutoff:
                        import shutil
                        shutil.rmtree(item, ignore_errors=True)
                        removed += 1
            except Exception as e:
                logger.warning(f"MaintenanceDaemon: failed to clean {item}: {e}")

        if removed > 0:
            logger.debug(f"MaintenanceDaemon: cleaned {removed} stale tmp items")

    def _verify_workspace_boundary(self) -> None:
        if not self.workspace_root.exists():
            return

        try:
            resolved = self.workspace_root.resolve()
            if not resolved.is_dir():
                logger.warning("MaintenanceDaemon: workspace root is not a directory")
        except Exception as e:
            logger.warning(f"MaintenanceDaemon: workspace boundary check failed: {e}")
