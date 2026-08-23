"""L2 Markdown Filing Cabinet."""

from __future__ import annotations

import re
from pathlib import Path
from loguru import logger
from ..models import MemoryEntry

SAFE_FILENAME_PATTERN = re.compile(r"[^a-z0-9_\-]")

class MarkdownStore:
    def __init__(self, l2_dir: Path):
        self.l2_dir = l2_dir

    def _get_path(self, entry: MemoryEntry) -> Path:
        safe_title = SAFE_FILENAME_PATTERN.sub("_", entry.metadata.get("title", "untitled").lower())[:50]
        filename = f"{str(entry.id)[:8]}_{safe_title}.md"
        return self.l2_dir / filename

    def write(self, entry: MemoryEntry) -> Path:
        self.l2_dir.mkdir(parents=True, exist_ok=True)
        path = self._get_path(entry)
        
        tags = entry.metadata.get("tags", [])
        tag_str = "[" + ", ".join(f'"{t}"' for t in tags) + "]"
        
        fm = [
            "---",
            f"id: {entry.id}",
            f"project_id: {entry.project_id}",
            f"title: {entry.metadata.get('title', '')}",
            f"tags: {tag_str}",
            f"created_at: {entry.created_at.isoformat()}",
            "---",
            "",
            entry.content
        ]
        path.write_text("\n".join(fm), encoding="utf-8")
        return path

    def delete(self, entry: MemoryEntry) -> bool:
        path = self._get_path(entry)
        if path.exists():
            path.unlink()
            return True
        return False
