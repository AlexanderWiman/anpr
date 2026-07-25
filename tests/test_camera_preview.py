import numpy as np

from src.config.settings import Settings
from src.services.camera_preview import preview_path, write_camera_preview


def test_write_camera_preview_creates_jpeg(tmp_path):
    settings = Settings(
        site_id="test",
        camera_id="cam-1",
        direction="entry",
        camera_rtsp_url="rtsp://127.0.0.1/stream1",
        backend_url="https://backend.example.com",
        anpr_agent_token="token",
        storage_dir=tmp_path / "storage",
        _env_file=None,
    )
    frame = np.zeros((120, 200, 3), dtype=np.uint8)

    path = write_camera_preview(settings, "cam-1", frame)

    assert path is not None
    assert path == preview_path(settings, "cam-1")
    assert path.is_file()
    assert path.stat().st_size > 0
