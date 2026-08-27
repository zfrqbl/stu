def test_memory_lifecycle_config_loaded(client):
    config = client.app.state.config
    assert config.memory.lifecycle.enabled is True
    assert config.memory.lifecycle.interval_seconds > 0


def test_memory_lifecycle_daemon_registered(client):
    manager = client.app.state.daemon_manager
    daemon = manager.get_daemon("memory_lifecycle")
    assert daemon is not None
    assert daemon.is_running


def test_memory_scoring_engine():
    from stu.memory.scoring import compute_composite_score
    from stu.config import MemoryLifecycleConfig

    config = MemoryLifecycleConfig()

    score = compute_composite_score(
        importance_score=0.8,
        access_count=10,
        last_accessed_at=None,
        config=config,
    )
    assert 0.0 <= score <= 1.0


def test_memory_archival_candidates():
    from stu.memory.archival import identify_archival_candidates

    memories = [
        {"id": "1", "status": "active", "composite_score": 0.1},
        {"id": "2", "status": "active", "composite_score": 0.9},
        {"id": "3", "status": "archived", "composite_score": 0.05},
    ]

    candidates = identify_archival_candidates(memories, score_threshold=0.15)
    assert len(candidates) == 1
    assert candidates[0]["id"] == "1"


def test_memory_pruning_candidates():
    from stu.memory.pruning import identify_pruning_candidates

    memories = [
        {"id": "1", "status": "active", "composite_score": 0.01, "memory_type": "episodic"},
        {"id": "2", "status": "active", "composite_score": 0.9, "memory_type": "semantic"},
        {"id": "3", "status": "archived", "composite_score": 0.1, "memory_type": "episodic"},
    ]

    candidates = identify_pruning_candidates(memories, critical_score_threshold=0.05)
    assert len(candidates) == 2
    ids = {c["id"] for c in candidates}
    assert "1" in ids
    assert "3" in ids


def test_memory_consolidation_candidates():
    from stu.memory.consolidation import identify_consolidation_candidates

    memories = [
        {"id": "1", "tags": ["python"]},
        {"id": "2", "tags": ["python"]},
        {"id": "3", "tags": ["python"]},
        {"id": "4", "tags": ["rust"]},
    ]

    clusters = identify_consolidation_candidates(memories, min_cluster_size=3)
    assert len(clusters) == 1
    assert len(clusters[0]) == 3


def test_memory_reflection_prompt():
    from stu.memory.reflection import build_reflection_prompt

    loop_state = {
        "goal": "Test the agent",
        "status": "completed",
        "current_phase": "persist",
        "plan": [
            {"description": "Step 1", "status": "completed"},
            {"description": "Step 2", "status": "completed"},
        ],
    }

    prompt = build_reflection_prompt(loop_state)
    assert "Test the agent" in prompt
    assert "completed" in prompt


def test_memory_migration_idempotent(tmp_path):
    from stu.memory.migrations import apply_migrations
    from pathlib import Path

    db_path = tmp_path / "test.sqlite3"
    apply_migrations(db_path)
    apply_migrations(db_path)

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT MAX(version) FROM schema_migrations")
    version = cursor.fetchone()[0]
    conn.close()

    assert version == 2
