"""Memory Archival Engine: move low-score memories to cold storage."""

from __future__ import annotations

from typing import Any

from loguru import logger


def identify_archival_candidates(
    memories: list[dict[str, Any]],
    score_threshold: float = 0.15,
) -> list[dict[str, Any]]:
    candidates = []
    for mem in memories:
        score = mem.get("composite_score", mem.get("importance_score", 0.5))
        status = mem.get("status", "active")
        if status == "active" and score < score_threshold:
            candidates.append(mem)
    return candidates


def archive_memory(mem: dict[str, Any]) -> dict[str, Any]:
    mem["status"] = "archived"
    return mem
