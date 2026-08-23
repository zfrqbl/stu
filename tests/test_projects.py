import pytest
from fastapi.testclient import TestClient
from stu.main import create_app

@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c

def test_list_projects(client):
    res = client.get("/api/v1/projects")
    assert res.status_code == 200
    assert any(p["id"] == "default" for p in res.json())


def test_create_and_get_project(client):
    res = client.post("/api/v1/projects", json={"id": "test-proj", "name": "Test"})
    assert res.status_code == 201, f"Failed to create project: {res.text}"

    res = client.get("/api/v1/projects/test-proj")
    assert res.status_code == 200
    assert res.json()["name"] == "Test"


def test_duplicate_project_fails(client):
    res1 = client.post("/api/v1/projects", json={"id": "dup-proj", "name": "Dup"})
    assert res1.status_code == 201, f"First create failed: {res1.text}"

    res2 = client.post("/api/v1/projects", json={"id": "dup-proj", "name": "Dup"})
    assert res2.status_code == 400
