"""Phase handlers for the 7-Phase Agentic Control Loop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from ..constants import LoopPhase, LoopStatus, ToolExecutionStatus
from ..llm.gateway import LLMGateway
from ..memory.service import MemoryService
from ..models import LoopState, MemoryCreateRequest, PlanStep
from ..tools.context import build_tool_context
from ..tools.executor import ToolExecutor


@dataclass
class ExecutionServices:
    llm: LLMGateway
    memory: MemoryService
    executor: ToolExecutor | None = None
    project_service: Any | None = None
    state_manager: Any | None = None
    config: Any | None = None
    workspace_root: Path | None = None


def _goal_title(state: LoopState, max_len: int = 80) -> str:
    return " ".join(state.goal.split())[:max_len]


async def handle_intake(state: LoopState, services: ExecutionServices) -> tuple[LoopState, bool]:
    logger.info(f"Loop {state.loop_id}: INTAKE")
    state.status = LoopStatus.RUNNING
    state.current_phase = LoopPhase.ORIENT
    return state, False


async def handle_orient(state: LoopState, services: ExecutionServices) -> tuple[LoopState, bool]:
    logger.info(f"Loop {state.loop_id}: ORIENT")
    memories = services.memory.list_memories(state.project_id, query=None)
    state.context["memories"] = [m.content[:200] for m in memories[:5]]
    state.current_phase = LoopPhase.PLAN
    return state, False


async def handle_plan(state: LoopState, services: ExecutionServices) -> tuple[LoopState, bool]:
    logger.info(f"Loop {state.loop_id}: PLAN")

    messages = [
        {"role": "system", "content": "You are a planner. Create a step-by-step plan."},
        {"role": "user", "content": f"Goal: {state.goal}"},
    ]
    await services.llm.generate(messages)

    goal_title = _goal_title(state)

    plan = [
        PlanStep(
            id="step-1",
            description="Retrieve project metadata",
            tool_name="project_get",
            args={},
        ),
        PlanStep(
            id="step-2",
            description="Persist execution memory",
            tool_name="memory_create",
            args={
                "title": f"Execution: {goal_title}",
                "content": f"Goal: {state.goal}",
                "tags": ["execution", "plan"],
            },
        ),
        PlanStep(
            id="step-3",
            description="Verify execution memory",
            tool_name="memory_search",
            args={
                "query": goal_title,
                "limit": 5,
            },
        ),
    ]

    state.plan = plan
    state.current_phase = LoopPhase.APPROVE
    state.status = LoopStatus.WAITING_FOR_HUMAN
    return state, True


async def handle_execute(state: LoopState, services: ExecutionServices) -> tuple[LoopState, bool]:
    logger.info(f"Loop {state.loop_id}: EXECUTE")

    if (
        not services.executor
        or not services.config
        or not services.workspace_root
        or not services.project_service
        or not services.state_manager
    ):
        state.status = LoopStatus.FAILED
        state.error = "Tool executor is not configured."
        return state, False

    context = build_tool_context(
        project_id=state.project_id,
        config=services.config,
        workspace_root=services.workspace_root,
        project_service=services.project_service,
        memory_service=services.memory,
        state_manager=services.state_manager,
    )

    for step in state.plan:
        step.status = "running"

        if not step.tool_name:
            step.status = "failed"
            step.result = "No tool_name provided."
            state.status = LoopStatus.FAILED
            state.error = "Plan step has no tool_name."
            return state, False

        result = await services.executor.invoke(step.tool_name, step.args, context)

        if result.status == ToolExecutionStatus.SUCCESS:
            step.status = "completed"
            step.result = str(result.output)[:1000]
        else:
            step.status = "failed"
            step.result = result.error
            state.status = LoopStatus.FAILED
            state.error = f"Tool {step.tool_name} failed: {result.error}"
            return state, False

    state.current_phase = LoopPhase.VERIFY
    return state, False


async def handle_verify(state: LoopState, services: ExecutionServices) -> tuple[LoopState, bool]:
    logger.info(f"Loop {state.loop_id}: VERIFY")

    results = "\n".join([f"{s.description}: {s.result}" for s in state.plan])
    messages = [
        {"role": "system", "content": "You are a verifier. Check if the goal was met."},
        {"role": "user", "content": f"Goal: {state.goal}\nResults:\n{results}"},
    ]

    response = await services.llm.generate(messages)
    state.context["verification"] = response
    state.current_phase = LoopPhase.PERSIST
    return state, False


async def handle_persist(state: LoopState, services: ExecutionServices) -> tuple[LoopState, bool]:
    logger.info(f"Loop {state.loop_id}: PERSIST")

    goal_title = _goal_title(state, max_len=50)
    content = f"Goal: {state.goal}\nStatus: {state.status}"

    verification = state.context.get("verification")
    if verification:
        content += f"\nVerification: {verification}"

    try:
        services.memory.create_memory(
            state.project_id,
            MemoryCreateRequest(
                title=f"Execution Result: {goal_title}",
                content=content,
                tags=["execution", "result"],
            ),
        )
    except Exception as e:
        logger.error(f"Failed to persist execution memory: {e}")

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
