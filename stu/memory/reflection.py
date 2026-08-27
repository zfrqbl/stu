"""Memory Reflection Engine: post-execution synthesis."""

from __future__ import annotations

from typing import Any

from loguru import logger


def build_reflection_prompt(loop_state: dict[str, Any]) -> str:
    goal = loop_state.get("goal", "Unknown goal")
    status = loop_state.get("status", "unknown")
    phase = loop_state.get("current_phase", "unknown")
    plan = loop_state.get("plan", [])

    plan_summary = "\n".join(
        f"- {step.get('description', 'Unknown step')}: {step.get('status', 'unknown')}"
        for step in plan
    )

    return (
        "You are a reflection engine for an autonomous agent. "
        "Based on the following execution loop, generate a concise reflection memory "
        "that captures: what was attempted, what succeeded, what failed, and what "
        "should be remembered for future similar tasks.\n\n"
        f"Goal: {goal}\n"
        f"Final Status: {status}\n"
        f"Final Phase: {phase}\n"
        f"Plan Steps:\n{plan_summary}\n\n"
        "Output a single paragraph reflection."
    )


def create_reflection_memory(
    loop_state: dict[str, Any],
    reflection_content: str,
) -> dict[str, Any]:
    return {
        "title": f"Reflection: {loop_state.get('goal', 'execution')[:50]}",
        "content": reflection_content,
        "tags": ["reflection", "execution", loop_state.get("loop_id", "unknown")],
        "memory_type": "reflection",
        "created_by": "reflection",
        "importance_score": 0.9,
    }
