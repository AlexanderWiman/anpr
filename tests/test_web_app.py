from datetime import datetime, timezone
from unittest.mock import MagicMock

import numpy as np
from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.services.camera_preview import write_camera_preview
from src.services.web_app import create_web_app


def _agent(tmp_path):
    agent = MagicMock()
    agent.settings.storage_dir = tmp_path / "storage"
    agent.pipelines = {"hall-1": MagicMock()}
    agent.history.list_recent.return_value = []
    agent.queue.all_events.return_value = []
    agent.delivery.refresh_backend_status = MagicMock()
    agent.delivery.queue_size = 0
    agent.delivery.stats = {"deliveries_succeeded": 0, "deliveries_failed": 0}
    agent.controller.status.return_value = {"state": "stopped"}
    return agent


def test_camera_preview_endpoint_returns_jpeg(tmp_path):
    settings = Settings(
        site_id="test",
        camera_id="hall-1",
        direction="entry",
        camera_rtsp_url="rtsp://127.0.0.1/stream1",
        backend_url="https://backend.example.com",
        anpr_agent_token="token",
        storage_dir=tmp_path / "storage",
        _env_file=None,
    )
    agent = _agent(tmp_path)
    agent.settings = settings
    agent.pipelines = {"hall-1": MagicMock()}

    write_camera_preview(settings, "hall-1", np.zeros((80, 120, 3), dtype=np.uint8))

    client = TestClient(create_web_app(agent, datetime.now(timezone.utc)))
    response = client.get("/api/cameras/hall-1/preview")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")


def test_crm_dashboard_served_at_root(tmp_path):
    agent = _agent(tmp_path)
    client = TestClient(create_web_app(agent, datetime.now(timezone.utc)))

    response = client.get("/")

    assert response.status_code == 200
    assert "ANPR Edge" in response.text
    assert "crm-dashboard.js" in response.text
