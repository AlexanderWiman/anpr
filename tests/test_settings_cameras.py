from pathlib import Path

import pytest

from src.config.settings import Settings


def _base_kwargs() -> dict:
    return {
        "site_id": "falun",
        "camera_id": "entrance-1",
        "direction": "entry",
        "camera_rtsp_url": "rtsp://127.0.0.1/stream1",
        "backend_url": "https://backend.example.com",
        "anpr_agent_token": "secret-token",
    }


def test_legacy_env_synthesizes_single_camera():
    settings = Settings(**_base_kwargs(), _env_file=None)

    assert len(settings.cameras) == 1
    assert settings.cameras[0].id == "entrance-1"
    assert settings.cameras[0].rtsp_url == "rtsp://127.0.0.1/stream1"
    assert settings.is_multi_camera is False
    assert settings.frames_dir_for("entrance-1") == settings.frames_dir


def test_cameras_json_loads_multiple_halls(tmp_path: Path):
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

    settings = Settings(
        **_base_kwargs(),
        cameras_config=cameras_file,
        _env_file=None,
    )

    assert settings.is_multi_camera is True
    assert [camera.id for camera in settings.cameras] == ["hall-1", "hall-2"]
    assert settings.camera_id == "hall-1"
    assert settings.camera_rtsp_url == "rtsp://127.0.0.1/hall1"
    assert settings.frames_dir_for("hall-1") == settings.frames_dir / "hall-1"
    assert settings.frames_dir_for("hall-2") == settings.frames_dir / "hall-2"


def test_cameras_json_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        Settings(
            **_base_kwargs(),
            cameras_config=tmp_path / "missing.json",
            _env_file=None,
        )


def test_falun_cameras_example_file_loads():
    cameras_file = Path("sites/falun.cameras.json")
    settings = Settings(
        **_base_kwargs(),
        cameras_config=cameras_file,
        _env_file=None,
    )

    assert settings.site_id == "falun"
    assert len(settings.cameras) == 2
    assert settings.cameras[0].id == "hall-1"
    assert settings.cameras[1].id == "hall-2"
