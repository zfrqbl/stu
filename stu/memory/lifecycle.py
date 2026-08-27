"""Memory Lifecycle Manager: orchestrates scoring, decay, consolidation, archival, pruning, reflection."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from ..config import MemoryLifecycleConfig
from .archival import archive_memory, identify_archival_candidates
from .consolidation import (
    build_consolidation_prompt,
    create_consolidated_memory,
    identify_consolidation_candidates,
)
from .pruning import (
    identify_pruning_candidates,
    is_hard_delete_eligible,
    soft_delete_memory,
)
from .reflection import build_reflection_prompt, create_reflection_memory
from .scoring import compute_composite_score


class MemoryLifecycleManager:
    def __init__(
        self,
        config: MemoryLifecycleConfig,
        memory_service=None,
        llm_gateway=None,
    ):
        self.config = config
        self.memory_service = memory_service
        self.llm_gateway = llm_gateway
        self._last_run_at: float | None = None
        self._cycle_count = 0
        self._stats: dict[str, int] = {
            "scored": 0,
            "archived": 0,
            "pruned": 0,
            "hard_deleted": 0,
            "consolidated": 0,
            "reflections": 0,
        }

    async def run_cycle(self, project_id: str) -> dict[str, Any]:
        start = time.time()
        self._cycle_count += 1

        report = {
            "cycle": self._cycle_count,
            "project_id": project_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "actions": {},
        }

        if not self.config.enabled:
            report["actions"]["skipped"] = "lifecycle disabled"
            return report

        if not self.memory_service:
            report["actions"]["skipped"] = "no memory service"
            return report

        try:
            memories = self._get_active_memories(project_id)

            scored_count = self._rescore_memories(memories, project_id)
            report["actions"]["scored"] = scored_count

            if self.config.archival_enabled:
                archived_count = self._run_archival(memories, project_id)
                report["actions"]["archived"] = archived_count

            if self.config.pruning_enabled:
                pruned_count = self._run_pruning(memories, project_id)
                report["actions"]["pruned"] = pruned_count

            if self.config.consolidation_enabled:
                consolidated_count = await self._run_consolidation(memories, project_id)
                report["actions"]["consolidated"] = consolidated_count

        except Exception as e:
            logger.error(f"Memory lifecycle cycle failed: {e}")
            report["actions"]["error"] = str(e)

        elapsed = time.time() - start
        report["duration_ms"] = elapsed * 1000
        self._last_run_at = time.time()

        logger.debug(f"Memory lifecycle cycle {self._cycle_count} completed in {elapsed:.2f}s")
        return report

    def _get_active_memories(self, project_id: str) -> list[dict[str, Any]]:
        try:
            entries = self.memory_service.list_memories(project_id, query=None)
            return [e.model_dump(mode="json") for e in entries]
        except Exception:
            return []

    def _rescore_memories(self, memories: list[dict[str, Any]], project_id: str) -> int:
        scored = 0
        for mem in memories:
            try:
                new_score = compute_composite_score(
                    importance_score=mem.get("importance_score", 0.5),
                    access_count=mem.get("access_count", 0),
                    last_accessed_at=mem.get("last_accessed_at"),
                    config=self.config,
                )
                mem["composite_score"] = new_score
                scored += 1
            except Exception:
                pass
        return scored

    def _run_archival(self, memories: list[dict[str, Any]], project_id: str) -> int:
        candidates = identify_archival_candidates(
            memories,
            score_threshold=self.config.archival_score_threshold,
        )

        archived = 0
        for mem in candidates:
            try:
                self.memory_service.archive_memory(project_id, mem["id"])
                archived += 1
            except Exception:
                pass

        return archived

    def _run_pruning(self, memories: list[dict[str, Any]], project_id: str) -> int:
        candidates = identify_pruning_candidates(
            memories,
            critical_score_threshold=self.config.pruning_critical_score_threshold,
        )

        pruned = 0
        for mem in candidates:
            try:
                if mem.get("status") == "archived":
                    self.memory_service.prune_memory(project_id, mem["id"])
                    pruned += 1
                elif mem.get("status") == "active":
                    self.memory_service.prune_memory(project_id, mem["id"])
                    pruned += 1
            except Exception:
                pass

        return pruned

    async def _run_consolidation(self, memories: list[dict[str, Any]], project_id: str) -> int:
        clusters = identify_consolidation_candidates(
            memories,
            min_cluster_size=self.config.consolidation_min_cluster_size,
        )

        consolidated = 0
        max_per_cycle = self.config.consolidation_max_per_cycle

        for cluster in clusters[:max_per_cycle]:
            if not self.llm_gateway:
                break

            try:
                prompt = build_consolidation_prompt(cluster)
                summary = await self.llm_gateway.generate([
                    {"role": "system", "content": "You are a memory consolidation engine."},
                    {"role": "user", "content": prompt},
                ])

                consolidated_data = create_consolidated_memory(cluster, summary)

                self.memory_service.create_memory_from_dict(project_id, consolidated_data)

                for mem in cluster:
                    self.memory_service.mark_consolidated(project_id, mem["id"])

                consolidated += 1
            except Exception as e:
                logger.warning(f"Consolidation failed for cluster: {e}")

        return consolidated

    async def run_reflection(self, project_id: str, loop_state: dict[str, Any]) -> bool:
        if not self.config.reflection_enabled:
            return False

        if not self.llm_gateway or not self.memory_service:
            return False

        try:
            prompt = build_reflection_prompt(loop_state)
            reflection_content = await self.llm_gateway.generate([
                {"role": "system", "content": "You are a reflection engine."},
                {"role": "user", "content": prompt},
            ])

            reflection_data = create_reflection_memory(loop_state, reflection_content)
            self.memory_service.create_memory_from_dict(project_id, reflection_data)
            self._stats["reflections"] += 1
            return True
        except Exception as e:
            logger.warning(f"Reflection failed: {e}")
            return False

    @property
    def stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "cycle_count": self._cycle_count,
            "last_run_at": self._last_run_at,
        }
