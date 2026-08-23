from fastapi.testclient import TestClient

from stu.main import create_app


def test_health_endpoint() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

        assert response.status_code == 200

        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["workspace_ready"] is True
        assert payload["version"] == "3.0.0"


def test_public_config_endpoint() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/config/public")

        assert response.status_code == 200

        payload = response.json()
        assert payload["app"]["name"] == "Project Stu"
        assert payload["app"]["default_project_id"] == "default"
        assert payload["llm_rate_limit"]["enabled"] is True
        assert payload["llm_rate_limit"]["min_interval_seconds"] == 2.0
        assert payload["llm_rate_limit"]["max_concurrency"] == 1
