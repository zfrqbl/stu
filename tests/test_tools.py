EXPECTED_TOOLS = {
    "memory_create",
    "memory_search",
    "memory_get",
    "project_get",
    "workspace_list",
    "workspace_read",
    "workspace_write",
    "system_status",
}


def test_tool_catalog_lists_all_native_tools(client):
    res = client.get("/api/v1/tools")
    assert res.status_code == 200

    names = {tool["name"] for tool in res.json()}
    assert EXPECTED_TOOLS.issubset(names)


def test_memory_tool_invocation(client):
    create_res = client.post(
        "/api/v1/projects/default/tools/invoke",
        json={
            "tool_name": "memory_create",
            "arguments": {
                "title": "Tool memory",
                "content": "Created through tool executor",
                "tags": ["tool"],
            },
        },
    )
    assert create_res.status_code == 200
    create_payload = create_res.json()
    assert create_payload["status"] == "success"

    search_res = client.post(
        "/api/v1/projects/default/tools/invoke",
        json={
            "tool_name": "memory_search",
            "arguments": {
                "query": "tool executor",
                "limit": 10,
            },
        },
    )
    assert search_res.status_code == 200
    search_payload = search_res.json()
    assert search_payload["status"] == "success"
    assert len(search_payload["output"]) > 0


def test_workspace_write_read_and_escape(client):
    write_res = client.post(
        "/api/v1/projects/default/tools/invoke",
        json={
            "tool_name": "workspace_write",
            "arguments": {
                "path": "hello.txt",
                "content": "hello tool",
            },
        },
    )
    assert write_res.status_code == 200
    write_payload = write_res.json()
    assert write_payload["status"] == "success"

    read_res = client.post(
        "/api/v1/projects/default/tools/invoke",
        json={
            "tool_name": "workspace_read",
            "arguments": {
                "path": "artifacts/hello.txt",
            },
        },
    )
    assert read_res.status_code == 200
    read_payload = read_res.json()
    assert read_payload["status"] == "success"
    assert read_payload["output"] == "hello tool"

    escape_res = client.post(
        "/api/v1/projects/default/tools/invoke",
        json={
            "tool_name": "workspace_read",
            "arguments": {
                "path": "../../stu.json",
            },
        },
    )
    assert escape_res.status_code == 200
    escape_payload = escape_res.json()
    assert escape_payload["status"] != "success"


def test_unknown_tool_is_blocked(client):
    res = client.post(
        "/api/v1/projects/default/tools/invoke",
        json={
            "tool_name": "does_not_exist",
            "arguments": {},
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] in {"blocked", "error"}
