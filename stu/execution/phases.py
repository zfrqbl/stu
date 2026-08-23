"""Phase handlers for the 7-Phase Agentic Control Loop."""

from __future__ import annotations

from loguru import logger

from ..models import LoopState, PlanStep, MemoryCreateRequest
from ..constants import LoopPhase, LoopStatus
from ..llm.gateway import LLMGateway
from ..memory.service import MemoryService


async def handle_intake(
    state: LoopState, llm: LLMGateway, memory: MemoryService
) -> tuple[LoopState, bool]:
    logger.info(f"Loop {state.loop_id}: INTAKE")
    state.status = LoopStatus.RUNNING
    state.current_phase = LoopPhase.ORIENT
    return state, False


async def handle_orient(
    state: LoopState, llm: LLMGateway, memory: MemoryService
) -> tuple[LoopState, bool]:
    logger.info(f"Loop {state.loop_id}: ORIENT")
    memories = memory.list_memories(state.project_id, query=None)
    state.context["memories"] = [m.content[:200] for m in memories[:5]]
    state.current_phase = LoopPhase.PLAN
    return state, False


async def handle_plan(
    state: LoopState, llm: LLMGateway, memory: MemoryService
) -> tuple[LoopState, bool]:
    logger.info(f"Loop {state.loop_id}: PLAN")
    messages = [
        {"role": "system", "content": "You are a planner. Create a step-by-step plan."},
        {"role": "user", "content": f"Goal: {state.goal}"},
    ]
    await llm.generate(messages)

    plan = [
        PlanStep(id="step-1", description="Analyze the request", tool_name="mock_analyzer"),
        PlanStep(id="step-2", description="Perform the action", tool_name="mock_actor"),
        PlanStep(id="step-3", description="Summarize the result", tool_name="mock_summarizer"),
    ]
    state.plan = plan
    state.current_phase = LoopPhase.APPROVE
    state.status = LoopStatus.WAITING_FOR_HUMAN
    return state, True


async def handle_execute(
    state: LoopState, llm: LLMGateway, memory: MemoryService
) -> tuple[LoopState, bool]:
    logger.info(f"Loop {state.loop_id}: EXECUTE")
    for step in state.plan:
        step.status = "running"
        step.result = f"Executed {step.tool_name} successfully"
        step.status = "completed"
    state.current_phase = LoopPhase.VERIFY
    return state, False


async def handle_verify(
    state: LoopState, llm: LLMGateway, memory: MemoryService
) -> tuple[LoopState, bool]:
    logger.info(f"Loop {state.loop_id}: VERIFY")
    results = "\n".join([f"{s.description}: {s.result}" for s in state.plan])
    messages = [
        {"role": "system", "content": "You are a verifier. Check if the goal was met."},
        {"role": "user", "content": f"Goal: {state.goal}\nResults:\n{results}"},
    ]
    response = await llm.generate(messages)
    state.context["verification"] = response
    state.current_phase = LoopPhase.PERSIST
    return state, False


async def handle_persist(
    state: LoopState, llm: LLMGateway, memory: MemoryService
) -> tuple[LoopState, bool]:
    logger.info(f"Loop {state.loop_id}: PERSIST")
    try:
        memory.create_memory(
            state.project_id,
            MemoryCreateRequest(
                title=f"Execution Result: {state.goal[:50]}",
                content=f"Goal: {state.goal}\nStatus: {state.status}\nVerification: {state.context.get('verification', '')}",
                tags=["execution", "result"],
            ),
        )
    except Exception as e:
        logger.error(f"Failed to persist memory: {e}")

    state.status = LoopStatus.COMPLETED
    return state, False


PHASE_HANDLERS = {
    LoopPhase.INTAKE: handle_intake,
    LoopPhase.ORIENT: handle_orient,
    LoopPhase.PLAN: handle_plan,
    LoopPhase.EXECUTE: handle_execute,
    LoopPhase.VERIFY: handle_verify,
    LoopPhase.PERSIST: handle_persist,
}
