import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from src.camera.base import CameraStatus
from src.camera.rtsp_capture import RTSPCaptureService
from src.config.cameras import CameraConfig
from src.config.settings import Settings


def _service(tmp_path: Path) -> RTSPCaptureService:
    settings = Settings(
        site_id="falun",
        camera_id="entrance-2",
        direction="entry",
        camera_rtsp_url="rtsp://127.0.0.1/stream1",
        backend_url="https://backend.example.com",
        anpr_agent_token="token",
        storage_dir=tmp_path / "storage",
        _env_file=None,
    )
    camera = CameraConfig(
        id="entrance-2",
        rtsp_url="rtsp://127.0.0.1/stream1",
        direction="entry",
    )
    return RTSPCaptureService(settings, camera)


def test_three_empty_frames_force_reconnect(tmp_path: Path):
    service = _service(tmp_path)
    fake_cap = MagicMock()
    fake_cap.isOpened.return_value = True
    fake_cap.read.return_value = (False, None)
    service._capture = fake_cap
    service._status = CameraStatus.CONNECTED

    async def run() -> None:
        for _ in range(3):
            result = await service.capture_frame(tmp_path / "frames")
            assert result is None

    asyncio.run(run())

    assert service.status == CameraStatus.RECONNECTING
    assert service._capture is None
    fake_cap.release.assert_called()
