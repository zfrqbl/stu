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

    config_data["workspace"]["root"] = str(workspace_dir)
    config_data["server"]["static_dir"] = str(PROJECT_ROOT / "static")
    config_data["llm"]["rate_limit"]["min_interval_seconds"] = 0.01

    security = config_data.setdefault("security", {})
    security["enable_guardrails"] = True
    security["enable_skill_sanitizer"] = True
    security.setdefault("forbidden_argument_patterns", []).append("TEST_FORBIDDEN")

    mcp = config_data.setdefault("mcp", {})
    mcp["enabled"] = True
    mcp.setdefault("allowed_stdio_commands", ["python", "python3", "uvx", "npx"])
    mcp.setdefault("servers", [
        {
            "name": "mock_server",
            "transport": "mock",
            "enabled": True,
            "tools": [
                {
                    "name": "echo",
                    "description": "Echoes back the input message",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "The message to echo"}
                        },
                        "required": ["message"],
                    },
                },
                {
                    "name": "add",
                    "description": "Adds two numbers together",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "number", "description": "First number"},
                            "b": {"type": "number", "description": "Second number"},
                        },
                        "required": ["a", "b"],
                    },
                },
            ],
        }
    ])

    daemons = config_data.setdefault("daemons", {})
    daemons["telemetry"] = {"enabled": True, "interval_seconds": 0.1, "priority": "high"}
    daemons["maintenance"] = {"enabled": True, "interval_seconds": 0.1, "priority": "high"}
    daemons["reporting"] = {"enabled": False, "interval_seconds": 0.1, "priority": "low"}

    temp_config_path = tmp_path / "stu.json"
    temp_config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    app = create_app(config_path=temp_config_path)

    with TestClient(app) as c:
        yield c
