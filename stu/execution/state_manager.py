"""State Manager: handles loop state persistence and crash recovery."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

from loguru import logger

from ..config import AppConfig
from ..models import LoopState, LoopStatus


class StateManager:
    def __init__(self, runtime_dir: Path, config: AppConfig):
        self.state_file = runtime_dir / config.execution.loop_state_filename
        self.debounce_seconds = config.execution.crash_recovery_debounce_seconds

    def load_state(self) -> LoopState | None:
        if not self.state_file.exists():
            return None
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return LoopState.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to load loop state: {e}")
            return None

    def save_state(self, state: LoopState) -> None:
        state.updated_at = datetime.now(timezone.utc)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(self.state_file)

    def check_crash_recovery(self) -> LoopState | None:
        state = self.load_state()
        if state is None:
            return None

        if state.status in [LoopStatus.COMPLETED, LoopStatus.FAILED, LoopStatus.IDLE]:
            return None

        now = datetime.now(timezone.utc)
        elapsed = (now - state.updated_at).total_seconds()

        if state.status == LoopStatus.RUNNING and elapsed < self.debounce_seconds:
            logger.warning("Crash recovery debounce triggered. Marking loop as failed.")
            state.status = LoopStatus.FAILED
            state.error = "Crash recovery debounce triggered."
            self.save_state(state)
            return None

        return state
