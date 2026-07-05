"""Multi-camera configuration — loaded from cameras.json or legacy .env fields."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class CameraConfig(BaseModel):
    """One RTSP camera / hall at a site."""

    id: str
    label: str | None = None
    direction: str = "entry"
    enabled: bool = True
    rtsp_url: str
    frame_interval_ms: int | None = None
    motion_gate_enabled: bool | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("camera id must not be empty")
        return cleaned

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("rtsp_url must not be empty")
        return cleaned


class CamerasFile(BaseModel):
    cameras: list[CameraConfig]

    @field_validator("cameras")
    @classmethod
    def validate_unique_ids(cls, cameras: list[CameraConfig]) -> list[CameraConfig]:
        ids = [camera.id for camera in cameras]
        if len(ids) != len(set(ids)):
            raise ValueError("camera ids must be unique")
        return cameras


def load_cameras_file(path: Path) -> list[CameraConfig]:
    """Load enabled cameras from a JSON file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    parsed = CamerasFile.model_validate(raw)
    return [camera for camera in parsed.cameras if camera.enabled]


def synthesize_legacy_camera(
    *,
    camera_id: str,
    direction: str,
    rtsp_url: str,
) -> CameraConfig:
    """Build a single-camera list from legacy .env fields."""
    return CameraConfig(
        id=camera_id,
        direction=direction,
        rtsp_url=rtsp_url,
    )


def resolve_cameras(
    *,
    cameras_config: Path | None,
    camera_id: str,
    direction: str,
    rtsp_url: str,
    remote_camera_config_enabled: bool = False,
) -> list[CameraConfig]:
    """
    Resolve the camera list for this agent.

    Uses cameras.json when configured; otherwise falls back to legacy env fields.
    When remote config is enabled, an empty local config is allowed at startup.
    """
    if cameras_config is not None:
        config_path = cameras_config.expanduser()
        if not config_path.is_file():
            raise FileNotFoundError(f"CAMERAS_CONFIG not found: {config_path}")
        cameras = load_cameras_file(config_path)
        if not cameras:
            raise ValueError(f"No enabled cameras in {config_path}")
        return cameras

    if not rtsp_url.strip():
        if remote_camera_config_enabled:
            return []
        raise ValueError("CAMERA_RTSP_URL is required when CAMERAS_CONFIG is not set")

    return [synthesize_legacy_camera(camera_id=camera_id, direction=direction, rtsp_url=rtsp_url)]
