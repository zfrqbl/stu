"""Global async rate limiter for all LLM requests."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from loguru import logger

from ..config import LlmRateLimitConfig


class LLMRateLimitTimeout(Exception):
    """Raised when an LLM request cannot acquire a rate limiter slot in time."""


class LLMRateLimiter:
    def __init__(self, config: LlmRateLimitConfig) -> None:
        self._config = config
        self._semaphore = asyncio.BoundedSemaphore(config.max_concurrency)
        self._interval_lock = asyncio.Lock()
        self._last_start: float | None = None

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    async def acquire(self) -> None:
        if not self._config.enabled:
            return

        wait_start = time.monotonic()

        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self._config.max_queue_wait_seconds,
            )
        except TimeoutError as exc:
            if self._config.fail_on_timeout:
                raise LLMRateLimitTimeout(
                    "Timed out waiting for LLM rate limiter semaphore."
                ) from exc

            if self._config.telemetry_events:
                logger.warning("LLM rate limiter semaphore wait exceeded timeout; continuing anyway.")

            await self._semaphore.acquire()

        async with self._interval_lock:
            now = time.monotonic()

            if self._config.min_interval_seconds > 0 and self._last_start is not None:
                required_wait = (self._last_start + self._config.min_interval_seconds) - now

                if required_wait > 0:
                    elapsed = time.monotonic() - wait_start
                    remaining_budget = max(0.0, self._config.max_queue_wait_seconds - elapsed)

                    if self._config.fail_on_timeout and required_wait > remaining_budget:
                        self._semaphore.release()
                        raise LLMRateLimitTimeout(
                            "LLM rate limiter interval wait exceeded remaining timeout budget."
                        )

                    if self._config.telemetry_events:
                        logger.debug(f"LLM rate limiter sleeping for {required_wait:.3f}s.")

                    await asyncio.sleep(required_wait)

            self._last_start = time.monotonic()

    def release(self) -> None:
        if not self._config.enabled:
            return
        self._semaphore.release()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        await self.acquire()
        try:
            yield
        finally:
            self.release()
