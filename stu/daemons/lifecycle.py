"""Memory Lifecycle Daemon: runs the memory lifecycle manager periodically."""

from __future__ import annotations

from loguru import logger

from .manager import Daemon


class MemoryLifecycleDaemon(Daemon):
    """Periodically runs memory scoring, decay, consolidation, archival, and pruning."""

    def __init__(
        self,
        interval_seconds: float,
        enabled: bool,
        lifecycle_manager=None,
        project_id: str = "default",
    ):
        super().__init__("memory_lifecycle", interval_seconds, enabled)
        self.lifecycle_manager = lifecycle_manager
        self.project_id = project_id

    async def tick(self) -> None:
        if not self.lifecycle_manager:
            return

        report = await self.lifecycle_manager.run_cycle(self.project_id)
        logger.debug(f"Memory lifecycle report: {report}")
