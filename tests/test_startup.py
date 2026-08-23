from fastapi.testclient import TestClient

from stu.main import create_app


def test_health_endpoint(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "ok"
    assert payload["workspace_ready"] is True
    assert payload["version"] == "3.0.0"


def test_public_config_endpoint(client):
    res = client.get("/api/v1/config/public")
    assert res.status_code == 200
    payload = res.json()
    assert payload["app"]["name"] == "Project Stu"
    assert payload["app"]["default_project_id"] == "default"
    assert payload["llm_rate_limit"]["enabled"] is True
    # conftest.py overrides this to 0.01 for fast tests, so we validate structure only
    assert payload["llm_rate_limit"]["min_interval_seconds"] > 0
    assert payload["llm_rate_limit"]["max_concurrency"] >= 1


def test_root_serves_index_html(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "<title>Project Stu v3.0</title>" in res.text


def test_static_css_is_served(client):
    res = client.get("/static/styles.css")
    assert res.status_code == 200
    assert "text/css" in res.headers["content-type"]
    assert ":root" in res.text
