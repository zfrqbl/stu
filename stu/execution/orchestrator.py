"""Orchestrator: drives the 7-Phase Agentic Control Loop."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from loguru import logger

from ..models import LoopState, LoopStatus
from ..constants import LoopPhase
from .state_manager import StateManager
from .phases import PHASE_HANDLERS
from ..llm.gateway import LLMGateway
from ..memory.service import MemoryService


class Orchestrator:
    def __init__(
        self,
        state_manager: StateManager,
        llm_gateway: LLMGateway,
        memory_service: MemoryService,
    ):
        self.state_manager = state_manager
        self.llm = llm_gateway
        self.memory = memory_service

    async def start_loop(self, project_id: str, goal: str) -> LoopState:
        loop_id = str(uuid4())
        state = LoopState(
            loop_id=loop_id,
            project_id=project_id,
            status=LoopStatus.RUNNING,
            current_phase=LoopPhase.INTAKE,
            goal=goal,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.state_manager.save_state(state)
        return await self.run_loop(state)

    async def run_loop(self, state: LoopState) -> LoopState:
        while state.status == LoopStatus.RUNNING:
            handler = PHASE_HANDLERS.get(state.current_phase)
            if not handler:
                state.status = LoopStatus.FAILED
                state.error = f"No handler for phase {state.current_phase}"
                self.state_manager.save_state(state)
                break

            try:
                state, should_yield = await handler(state, self.llm, self.memory)
                self.state_manager.save_state(state)
                if should_yield:
                    break
            except Exception as e:
                logger.error(f"Loop {state.loop_id} failed in phase {state.current_phase}: {e}")
                state.status = LoopStatus.FAILED
                state.error = str(e)
                self.state_manager.save_state(state)
                break

        return state

    async def resume_loop(self, state: LoopState, approved: bool) -> LoopState:
        if state.current_phase != LoopPhase.APPROVE:
            raise ValueError("Can only resume from APPROVE phase")

        if not approved:
            state.status = LoopStatus.FAILED
            state.error = "Rejected by user"
            self.state_manager.save_state(state)
            return state

        state.current_phase = LoopPhase.EXECUTE
        state.status = LoopStatus.RUNNING
        self.state_manager.save_state(state)
        return await self.run_loop(state)
