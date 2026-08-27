def test_security_status(client):
    res = client.get("/api/v1/security/status")
    assert res.status_code == 200

    payload = res.json()
    assert payload["guardrails_enabled"] is True
    assert payload["sanitizer_enabled"] is True
    assert payload["network_enabled"] is False
    assert payload["event_retention"] > 0


def test_forbidden_tool_argument_is_blocked(client):
    res = client.post(
        "/api/v1/projects/default/tools/invoke",
        json={
            "tool_name": "memory_create",
            "arguments": {
                "title": "Blocked memory",
                "content": "This contains TEST_FORBIDDEN content",
                "tags": ["security"],
            },
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "blocked"
    assert payload["output"] is None

    events_res = client.get("/api/v1/security/events?limit=10")
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) > 0


def test_forbidden_execution_goal_is_blocked(client):
    res = client.post(
        "/api/v1/projects/default/execution/start",
        json={"goal": "This goal contains TEST_FORBIDDEN"},
    )

    assert res.status_code == 403


def test_path_traversal_is_blocked(client):
    res = client.post(
        "/api/v1/projects/default/tools/invoke",
        json={
            "tool_name": "workspace_read",
            "arguments": {
                "path": "../../stu.json",
            },
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] in {"blocked", "error"}


def test_safe_tool_still_works(client):
    res = client.post(
        "/api/v1/projects/default/tools/invoke",
        json={
            "tool_name": "project_get",
            "arguments": {},
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "success"
