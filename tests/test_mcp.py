def test_mcp_servers_listed(client):
    res = client.get("/api/v1/mcp/servers")
    assert res.status_code == 200

    servers = res.json()
    assert len(servers) > 0

    mock_server = next((s for s in servers if s["name"] == "mock_server"), None)
    assert mock_server is not None
    assert mock_server["status"] == "connected"
    assert mock_server["transport"] == "mock"
    assert mock_server["tools_count"] > 0


def test_mcp_server_tools_listed(client):
    res = client.get("/api/v1/mcp/servers/mock_server/tools")
    assert res.status_code == 200

    tools = res.json()
    assert len(tools) > 0

    tool_names = [t["tool_name"] for t in tools]
    assert "echo" in tool_names
    assert "add" in tool_names

    for tool in tools:
        assert tool["server_name"] == "mock_server"
        assert tool["schema_valid"] is True


def test_mcp_echo_tool_via_catalog(client):
    res = client.post(
        "/api/v1/projects/default/tools/invoke",
        json={
            "tool_name": "mcp_mock_server_echo",
            "arguments": {"message": "hello from test"},
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "success"
    assert "hello from test" in str(payload["output"])


def test_mcp_add_tool_via_catalog(client):
    res = client.post(
        "/api/v1/projects/default/tools/invoke",
        json={
            "tool_name": "mcp_mock_server_add",
            "arguments": {"a": 3, "b": 7},
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "success"
    assert "10" in str(payload["output"])


def test_mcp_tool_not_found(client):
    res = client.get("/api/v1/mcp/servers/nonexistent_server/tools")
    assert res.status_code == 404


def test_mcp_disabled_server_not_connected(client):
    res = client.get("/api/v1/mcp/servers")
    assert res.status_code == 200

    servers = res.json()
    for server in servers:
        if not server["enabled"]:
            assert server["status"] in {"disconnected", "error"}
