def test_daemon_manager_status(client):
    manager = client.app.state.daemon_manager
    status = manager.get_status()

    assert len(status) == 3

    names = [d["name"] for d in status]
    assert "telemetry" in names
    assert "maintenance" in names
    assert "reporting" in names


def test_telemetry_daemon_running(client):
    manager = client.app.state.daemon_manager
    daemon = manager.get_daemon("telemetry")
    assert daemon is not None
    assert daemon.is_running


def test_maintenance_daemon_running(client):
    manager = client.app.state.daemon_manager
    daemon = manager.get_daemon("maintenance")
    assert daemon is not None
    assert daemon.is_running


def test_reporting_daemon_disabled_in_tests(client):
    manager = client.app.state.daemon_manager
    daemon = manager.get_daemon("reporting")
    assert daemon is not None
    assert not daemon.is_running


def test_websocket_telemetry_endpoint(client):
    with client.websocket_connect("/api/v1/telemetry/ws") as ws:
        ws.send_text("ping")
        response = ws.receive_text()
        assert response == "pong"
