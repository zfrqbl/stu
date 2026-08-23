import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stu.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="function")
def client(tmp_path):
    workspace_dir = tmp_path / "workspace"

    default_config_path = PROJECT_ROOT / "stu.json"
    if not default_config_path.exists():
        pytest.fail("Default stu.json not found in project root.")

    config_data = json.loads(default_config_path.read_text(encoding="utf-8"))

    # Isolate runtime data.
    config_data["workspace"]["root"] = str(workspace_dir)

    # Keep static assets pointing to the real frontend files.
    config_data["server"]["static_dir"] = str(PROJECT_ROOT / "static")

    temp_config_path = tmp_path / "stu.json"
    temp_config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    app = create_app(config_path=temp_config_path)

    with TestClient(app) as c:
        yield c
