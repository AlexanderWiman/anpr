import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from src.camera.base import CameraStatus
from src.camera.rtsp_capture import RTSPCaptureService
from src.config.cameras import CameraConfig
from src.config.settings import Settings


def _service(tmp_path: Path, *, empty_reconnect: int = 1) -> RTSPCaptureService:
    settings = Settings(
        site_id="falun",
        camera_id="entrance-2",
        direction="entry",
        camera_rtsp_url="rtsp://127.0.0.1/stream1",
        backend_url="https://backend.example.com",
        anpr_agent_token="token",
        storage_dir=tmp_path / "storage",
        rtsp_empty_frame_reconnect=empty_reconnect,
        rtsp_max_session_seconds=40,
        _env_file=None,
    )
    camera = CameraConfig(
        id="entrance-2",
        rtsp_url="rtsp://127.0.0.1/stream1",
        direction="entry",
    )
    return RTSPCaptureService(settings, camera)


def test_empty_frame_forces_reconnect(tmp_path: Path):
    service = _service(tmp_path, empty_reconnect=1)
    fake_cap = MagicMock()
    fake_cap.isOpened.return_value = True
    fake_cap.read.return_value = (False, None)
    service._capture = fake_cap
    service._status = CameraStatus.CONNECTED

    async def run() -> None:
        result = await service.capture_frame(tmp_path / "frames")
        assert result is None

    asyncio.run(run())

    assert service.status == CameraStatus.RECONNECTING
    assert service._capture is None
    fake_cap.release.assert_called()


def test_max_session_triggers_refresh_path(tmp_path: Path):
    service = _service(tmp_path)
    fake_cap = MagicMock()
    fake_cap.isOpened.return_value = True
    service._capture = fake_cap
    service._status = CameraStatus.CONNECTED
    service._session_started_at = 0.0
    service._settings = service._settings.model_copy(
        update={"rtsp_reconnect_delay_ms": 1, "rtsp_connect_timeout_ms": 100}
    )

    async def run() -> bool:
        return await service.ensure_connected()

    ok = asyncio.run(run())
    assert ok is False
    assert service._capture is None
    fake_cap.release.assert_called()
