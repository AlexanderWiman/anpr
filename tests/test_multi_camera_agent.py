import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.config.settings import Settings
from src.models.detection import PlateDetection
from src.services.agent import AnprAgent
from src.services.status_report import build_status_report


def _settings(tmp_path: Path) -> Settings:
    cameras_file = tmp_path / "cameras.json"
    cameras_file.write_text(
        """
        {
          "cameras": [
            {"id": "hall-1", "label": "Hall 1", "rtsp_url": "rtsp://127.0.0.1/hall1"},
            {"id": "hall-2", "label": "Hall 2", "rtsp_url": "rtsp://127.0.0.1/hall2"}
          ]
        }
        """,
        encoding="utf-8",
    )
    return Settings(
        site_id="falun",
        camera_id="hall-1",
        direction="entry",
        camera_rtsp_url="",
        cameras_config=cameras_file,
        backend_url="https://backend.example.com",
        anpr_agent_token="secret-token",
        storage_dir=tmp_path / "storage",
        log_dir=tmp_path / "logs",
        motion_gate_enabled=False,
        agent_auto_start=False,
        heartbeat_enabled=False,
        booking_hints_enabled=False,
        _env_file=None,
    )


def test_agent_creates_pipeline_per_camera(tmp_path: Path):
    agent = AnprAgent(_settings(tmp_path))

    assert set(agent.pipelines.keys()) == {"hall-1", "hall-2"}
    assert agent.pipelines["hall-1"].capture._camera.rtsp_url == "rtsp://127.0.0.1/hall1"
    assert agent.pipelines["hall-2"].capture._camera.rtsp_url == "rtsp://127.0.0.1/hall2"


def test_process_frame_tags_event_with_camera_id(tmp_path: Path):
    agent = AnprAgent(_settings(tmp_path))
    frame_path = tmp_path / "frame.png"
    frame_path.write_bytes(b"png")

    detections = [
        PlateDetection(plate="ABC123", confidence=0.9, provider="yolo_ocr"),
        PlateDetection(plate="ABC123", confidence=0.92, provider="yolo_ocr"),
    ]
    agent._provider.detect_plate = AsyncMock(side_effect=[detections[:1], detections[1:]])
    agent.delivery.submit = AsyncMock(return_value=True)

    asyncio.run(agent.process_frame(frame_path, "hall-1"))
    delivered = asyncio.run(agent.process_frame(frame_path, "hall-1"))

    assert delivered is True
    event = agent.delivery.submit.await_args.args[0]
    assert event.camera_id == "hall-1"
    assert event.site_id == "falun"


def test_site_wide_dedup_blocks_second_hall(tmp_path: Path):
    agent = AnprAgent(_settings(tmp_path))
    frame_path = tmp_path / "frame.png"
    frame_path.write_bytes(b"png")

    detection = [PlateDetection(plate="ABC123", confidence=0.9, provider="yolo_ocr")]
    agent._provider.detect_plate = AsyncMock(return_value=detection)
    agent.delivery.submit = AsyncMock(return_value=True)

    asyncio.run(agent.process_frame(frame_path, "hall-1"))
    asyncio.run(agent.process_frame(frame_path, "hall-1"))
    assert agent.delivery.submit.await_count == 1

    asyncio.run(agent.process_frame(frame_path, "hall-2"))
    asyncio.run(agent.process_frame(frame_path, "hall-2"))
    assert agent.delivery.submit.await_count == 1


def test_status_report_includes_camera_list(tmp_path: Path):
    agent = AnprAgent(_settings(tmp_path))
    report = build_status_report(agent, datetime.now(timezone.utc))

    assert report["site"]["cameraCount"] == 2
    assert [camera["id"] for camera in report["cameras"]] == ["hall-1", "hall-2"]


@patch("src.services.agent_controller.asyncio.create_task")
def test_controller_starts_capture_loop_per_camera(mock_create_task, tmp_path: Path):
    mock_create_task.side_effect = lambda coro, **kwargs: MagicMock(name=kwargs.get("name"))
    agent = AnprAgent(_settings(tmp_path))

    async def run():
        result = await agent.controller.start()
        assert result["ok"] is True
        names = [call.kwargs.get("name") for call in mock_create_task.call_args_list]
        assert "capture-loop-hall-1" in names
        assert "capture-loop-hall-2" in names

    asyncio.run(run())
