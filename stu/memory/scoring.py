"""Memory Scoring Engine: multi-factor composite scoring."""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone

from ..config import MemoryLifecycleConfig


def compute_recency_score(last_accessed_at: str | None, half_life_hours: float) -> float:
    if not last_accessed_at:
        return 0.5

    try:
        last_dt = datetime.fromisoformat(last_accessed_at)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_hours = (now - last_dt).total_seconds() / 3600.0
        if age_hours <= 0:
            return 1.0
        return math.exp(-0.693 * age_hours / half_life_hours)
    except (ValueError, TypeError):
        return 0.5


def compute_frequency_score(access_count: int) -> float:
    if access_count <= 0:
        return 0.0
    return min(1.0, math.log1p(access_count) / math.log1p(100))


def compute_composite_score(
    importance_score: float,
    access_count: int,
    last_accessed_at: str | None,
    config: MemoryLifecycleConfig,
) -> float:
    recency = compute_recency_score(last_accessed_at, config.scoring_decay_half_life_hours)
    frequency = compute_frequency_score(access_count)
    importance = max(0.0, min(1.0, importance_score))

    composite = (
        config.scoring_w_recency * recency
        + config.scoring_w_frequency * frequency
        + config.scoring_w_importance * importance
    )

    return max(0.0, min(1.0, composite))
