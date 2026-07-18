"""Tests for remote heartbeat."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx

from src.config.settings import Settings
from src.services.backend_client import BackendClient
from src.services.heartbeat import HeartbeatService


def _settings() -> Settings:
    return Settings(
        site_id="falun",
        camera_id="entrance-1",
        direction="entry",
        camera_rtsp_url="rtsp://127.0.0.1/stream1",
        backend_url="https://backend.example.com",
        anpr_agent_token="secret-token",
        heartbeat_enabled=True,
        heartbeat_interval_seconds=60,
        _env_file=None,
    )


def test_send_heartbeat_posts_to_site_url():
    client = BackendClient(_settings())
    response = httpx.Response(
        200,
        request=httpx.Request(
            "POST",
            "https://backend.example.com/api/anpr/sites/falun/heartbeat",
        ),
        json={"ok": True},
    )
    client._client.post = AsyncMock(return_value=response)  # noqa: SLF001

    result = asyncio.run(client.send_heartbeat({"site": {"siteId": "falun"}}))

    assert result == {"ok": True}
    client._client.post.assert_awaited_once()
    args, kwargs = client._client.post.await_args
    assert args[0].endswith("/api/anpr/sites/falun/heartbeat")
    assert kwargs["json"]["site"]["siteId"] == "falun"


def test_heartbeat_builds_payload_from_agent():
    from collections import deque

    settings = _settings()
    agent = MagicMock()
    agent.settings = settings
    agent.controller.status.return_value = {"state": "running"}
    agent.camera.source_type = "rtsp"
    agent.camera.status.value = "connected"
    agent.camera.last_frame_at = datetime.now(timezone.utc)
    agent.camera.frames_captured = 10
    agent.primary_pipeline.capture = agent.camera
    agent.primary_pipeline.camera_id = "entrance-1"
    agent.primary_pipeline.label = "entrance-1"
    agent.primary_pipeline.direction = "entry"
    agent.primary_pipeline.config.rtsp_url = "rtsp://127.0.0.1/stream1"
    agent.pipelines = {"entrance-1": agent.primary_pipeline}
    agent.provider_name = "yolo_ocr"
    agent._ocr_busy = False
    agent._ocr_queue = deque()
    agent.remote_camera_config.status.return_value = {"enabled": False}
    agent.delivery.refresh_backend_status = AsyncMock()
    agent.delivery.backend_status.as_dict.return_value = {
        "ok": True,
        "code": "ok",
        "detail": "https://backend.example.com",
        "reachable": True,
    }
    agent.delivery.queue_size = 0
    agent.delivery.stats = {"deliveries_succeeded": 1, "deliveries_failed": 0}
    agent.booking_hints.status.return_value = {"enabled": True, "plateCount": 3}
    agent.heartbeat.status.return_value = {"enabled": True, "intervalSeconds": 30}
    agent.deduplicator.last_detection = None
    agent.backend.send_heartbeat = AsyncMock(return_value={"ok": True})

    started = datetime.now(timezone.utc)
    service = HeartbeatService(agent, started)

    assert asyncio.run(service.send_once()) is True
    payload = agent.backend.send_heartbeat.await_args.args[0]
    assert payload["site"]["siteId"] == "falun"
    assert payload["camera"]["status"] == "connected"
    assert payload["agent"]["state"] == "running"
    assert isinstance(payload["host"]["hostname"], str)
    assert payload["host"]["hostname"]
