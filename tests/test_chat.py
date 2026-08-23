def test_chat_send_and_receive(client):
    res = client.post("/api/v1/projects/default/chat", json={"message": "Hello, Stu!"})
    assert res.status_code == 200
    data = res.json()
    assert data["message"]["role"] == "assistant"
    assert "Mock LLM" in data["message"]["content"]
    assert data["project_id"] == "default"


def test_chat_history(client):
    client.post("/api/v1/projects/default/chat", json={"message": "Test message"})

    res = client.get("/api/v1/projects/default/chat/history")
    assert res.status_code == 200
    history = res.json()
    assert len(history) >= 2
    assert history[-2]["role"] == "user"
    assert history[-1]["role"] == "assistant"


def test_chat_project_not_found(client):
    res = client.post("/api/v1/projects/nonexistent/chat", json={"message": "Hello"})
    assert res.status_code == 404


def test_chat_empty_message(client):
    res = client.post("/api/v1/projects/default/chat", json={"message": ""})
    assert res.status_code == 422


def test_chat_history_empty(client):
    res = client.get("/api/v1/projects/default/chat/history")
    assert res.status_code == 200
    assert res.json() == []
