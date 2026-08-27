"""Memory Decay Engine: time-based score reduction."""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import MemoryLifecycleConfig
from .scoring import compute_composite_score


def apply_decay(
    importance_score: float,
    access_count: int,
    last_accessed_at: str | None,
    memory_type: str,
    config: MemoryLifecycleConfig,
) -> float:
    half_life_map = {
        "episodic": config.decay_episodic_half_life_hours,
        "semantic": config.decay_semantic_half_life_hours,
        "procedural": config.decay_procedural_half_life_hours,
        "reflection": config.decay_reflection_half_life_hours,
    }

    half_life = half_life_map.get(memory_type, config.scoring_decay_half_life_hours)

    return compute_composite_score(
        importance_score=importance_score,
        access_count=access_count,
        last_accessed_at=last_accessed_at,
        config=config,
    )
