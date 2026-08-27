"""ReportingDaemon: generates periodic project summaries via LLM."""

from __future__ import annotations

import time

from loguru import logger

from .manager import Daemon


class ReportingDaemon(Daemon):
    """Generates periodic execution summaries and saves to L2 memory."""

    def __init__(
        self,
        interval_seconds: float,
        enabled: bool,
        state_manager=None,
        memory_service=None,
        llm_gateway=None,
        project_id: str = "default",
    ):
        super().__init__("reporting", interval_seconds, enabled)
        self.state_manager = state_manager
        self.memory_service = memory_service
        self.llm_gateway = llm_gateway
        self.project_id = project_id
        self._last_report_time: float | None = None

    async def tick(self) -> None:
        if not self.state_manager or not self.memory_service or not self.llm_gateway:
            return

        try:
            state = self.state_manager.load_state()
            if not state:
                return

            if state.status.value not in ("completed", "failed"):
                return

            if self._last_report_time and time.time() - self._last_report_time < self.interval_seconds:
                return

            summary_prompt = (
                f"Summarize this execution loop in 2-3 sentences:\n"
                f"Goal: {state.goal}\n"
                f"Status: {state.status.value}\n"
                f"Phase reached: {state.current_phase.value}\n"
                f"Project: {state.project_id}"
            )

            messages = [
                {"role": "system", "content": "You are a concise technical summarizer."},
                {"role": "user", "content": summary_prompt},
            ]

            summary = await self.llm_gateway.generate(messages)

            from ..models import MemoryCreateRequest

            self.memory_service.create_memory(
                self.project_id,
                MemoryCreateRequest(
                    title=f"Execution Report: {state.goal[:50]}",
                    content=summary,
                    tags=["report", "execution", "auto-generated"],
                ),
            )

            self._last_report_time = time.time()
            logger.info(f"ReportingDaemon: generated execution report for project '{self.project_id}'")

        except Exception as e:
            logger.warning(f"ReportingDaemon tick failed: {e}")
