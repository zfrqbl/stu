"""DaemonManager: manages background daemon lifecycle."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine

from loguru import logger


class Daemon:
    """Base daemon class. Subclass and implement tick()."""

    def __init__(self, name: str, interval_seconds: float, enabled: bool = True):
        self.name = name
        self.interval_seconds = interval_seconds
        self.enabled = enabled
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_run_at: float | None = None
        self._error_count = 0

    async def tick(self) -> None:
        """Override in subclass. Called every interval_seconds."""
        raise NotImplementedError

    async def start(self) -> None:
        if not self.enabled:
            logger.debug(f"Daemon '{self.name}' is disabled, skipping start")
            return

        if self._running:
            logger.warning(f"Daemon '{self.name}' is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Daemon '{self.name}' started (interval={self.interval_seconds}s)")

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info(f"Daemon '{self.name}' stopped")

    async def _run_loop(self) -> None:
        import time

        while self._running:
            try:
                self._last_run_at = time.time()
                await self.tick()
                self._error_count = 0
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._error_count += 1
                logger.error(f"Daemon '{self.name}' tick failed (count={self._error_count}): {e}")

            await asyncio.sleep(self.interval_seconds)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def error_count(self) -> int:
        return self._error_count


class DaemonManager:
    """Registers and manages all daemons."""

    def __init__(self):
        self._daemons: dict[str, Daemon] = {}

    def register(self, daemon: Daemon) -> None:
        if daemon.name in self._daemons:
            raise ValueError(f"Daemon '{daemon.name}' is already registered")
        self._daemons[daemon.name] = daemon

    async def start_all(self) -> None:
        for daemon in self._daemons.values():
            await daemon.start()

    async def stop_all(self) -> None:
        for daemon in self._daemons.values():
            await daemon.stop()

    def get_daemon(self, name: str) -> Daemon | None:
        return self._daemons.get(name)

    def get_all_daemons(self) -> list[Daemon]:
        return list(self._daemons.values())

    def get_status(self) -> list[dict[str, Any]]:
        import time

        statuses = []
        for daemon in self._daemons.values():
            statuses.append({
                "name": daemon.name,
                "enabled": daemon.enabled,
                "running": daemon.is_running,
                "interval_seconds": daemon.interval_seconds,
                "last_run_at": daemon._last_run_at,
                "error_count": daemon.error_count,
            })
        return statuses
