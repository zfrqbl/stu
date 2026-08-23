import pytest
from fastapi.testclient import TestClient
from stu.main import create_app

@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c

def test_memory_crud(client):
    # Create
    res = client.post("/api/v1/projects/default/memory", json={
        "title": "Test Memory", "content": "Hello world", "tags": ["test"]
    })
    assert res.status_code == 201
    mem_id = res.json()["id"]

    # Read
    res = client.get(f"/api/v1/projects/default/memory/{mem_id}")
    assert res.status_code == 200
    assert res.json()["title"] == "Test Memory"

    # List
    res = client.get("/api/v1/projects/default/memory")
    assert res.status_code == 200
    assert len(res.json()) > 0

    # Delete
    res = client.delete(f"/api/v1/projects/default/memory/{mem_id}")
    assert res.status_code == 204

    # Verify deleted
    res = client.get(f"/api/v1/projects/default/memory/{mem_id}")
    assert res.status_code == 404

def test_memory_search(client):
    client.post("/api/v1/projects/default/memory", json={
        "title": "Searchable Item", "content": "Unique keyword xyz123", "tags": []
    })
    res = client.get("/api/v1/projects/default/memory?query=xyz123")
    assert res.status_code == 200
    assert any("xyz123" in m["content"] for m in res.json())
