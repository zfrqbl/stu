"""Memory Consolidation Engine: merge similar memories."""

from __future__ import annotations

from typing import Any

from loguru import logger


def identify_consolidation_candidates(
    memories: list[dict[str, Any]],
    min_cluster_size: int = 3,
) -> list[list[dict[str, Any]]]:
    tag_groups: dict[str, list[dict[str, Any]]] = {}

    for mem in memories:
        tags = mem.get("tags", [])
        for tag in tags:
            if tag not in tag_groups:
                tag_groups[tag] = []
            tag_groups[tag].append(mem)

    clusters = []
    seen_ids = set()

    for tag, group in tag_groups.items():
        if len(group) >= min_cluster_size:
            cluster_ids = {m["id"] for m in group}
            if not cluster_ids.issubset(seen_ids):
                clusters.append(group)
                seen_ids.update(cluster_ids)

    return clusters


def build_consolidation_prompt(cluster: list[dict[str, Any]]) -> str:
    entries = []
    for mem in cluster:
        entries.append(f"- {mem.get('title', 'Untitled')}: {mem.get('content', '')[:200]}")

    entries_text = "\n".join(entries)

    return (
        "You are a memory consolidation engine. "
        "Merge the following related memories into a single, concise summary memory. "
        "Preserve key facts and remove redundancy. "
        "Output only the consolidated memory content.\n\n"
        f"Memories to consolidate:\n{entries_text}"
    )


def create_consolidated_memory(
    cluster: list[dict[str, Any]],
    summary_content: str,
) -> dict[str, Any]:
    all_tags = set()
    for mem in cluster:
        all_tags.update(mem.get("tags", []))

    return {
        "title": f"Consolidated: {cluster[0].get('title', 'memories')[:50]}",
        "content": summary_content,
        "tags": sorted(list(all_tags)),
        "memory_type": "semantic",
        "created_by": "consolidation",
        "importance_score": 0.8,
        "consolidated_from": [m["id"] for m in cluster],
    }
