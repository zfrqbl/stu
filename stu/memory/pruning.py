"""Memory Pruning Engine: safe deletion with grace period."""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger


def identify_pruning_candidates(
    memories: list[dict[str, Any]],
    critical_score_threshold: float = 0.05,
) -> list[dict[str, Any]]:
    candidates = []
    for mem in memories:
        status = mem.get("status", "active")
        score = mem.get("composite_score", mem.get("importance_score", 0.5))
        memory_type = mem.get("memory_type", "episodic")

        if status == "active" and score < critical_score_threshold:
            candidates.append(mem)
        elif status == "archived" and memory_type == "episodic":
            candidates.append(mem)

    return candidates


def soft_delete_memory(mem: dict[str, Any]) -> dict[str, Any]:
    mem["status"] = "pruned"
    mem["pruned_at"] = datetime.now(timezone.utc).isoformat()
    return mem


def is_hard_delete_eligible(
    mem: dict[str, Any],
    grace_period_hours: float = 168.0,
) -> bool:
    if mem.get("status") != "pruned":
        return False

    pruned_at = mem.get("pruned_at")
    if not pruned_at:
        return True

    try:
        pruned_dt = datetime.fromisoformat(pruned_at)
        if pruned_dt.tzinfo is None:
            pruned_dt = pruned_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        hours_since = (now - pruned_dt).total_seconds() / 3600.0
        return hours_since >= grace_period_hours
    except (ValueError, TypeError):
        return True
