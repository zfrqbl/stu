def test_execution_full_flow(client):
    # Start execution
    res = client.post("/api/v1/projects/default/execution/start", json={"goal": "Test the agent"})
    assert res.status_code == 200
    state = res.json()
    assert state["status"] == "waiting_for_human"
    assert state["current_phase"] == "approve"
    assert len(state["plan"]) > 0

    # Approve execution
    res = client.post("/api/v1/projects/default/execution/approve")
    assert res.status_code == 200
    state = res.json()
    assert state["status"] == "completed"
    assert state["current_phase"] == "persist"


def test_execution_reject(client):
    # Start execution
    client.post("/api/v1/projects/default/execution/start", json={"goal": "Reject me"})
    
    # Reject execution
    res = client.post("/api/v1/projects/default/execution/reject")
    assert res.status_code == 200
    state = res.json()
    assert state["status"] == "failed"
    assert state["error"] == "Rejected by user"


def test_execution_status_idle(client):
    res = client.get("/api/v1/projects/default/execution/status")
    assert res.status_code == 200
    state = res.json()
    assert state["status"] == "idle"


def test_execution_project_not_found(client):
    res = client.post("/api/v1/projects/nonexistent/execution/start", json={"goal": "Hello"})
    assert res.status_code == 404
