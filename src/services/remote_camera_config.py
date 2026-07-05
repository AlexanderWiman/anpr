"""Poll backend for structured camera configuration (dev feature)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from src.config.cameras import CameraConfig
from src.utils.logging import get_logger
from src.utils.rtsp_url import build_rtsp_url, mask_stream_url

if TYPE_CHECKING:
    from src.services.agent import AnprAgent

logger = get_logger(__name__)


def camera_configs_from_remote_payload(payload: dict) -> list[CameraConfig]:
    raw_cameras = payload.get("cameras")
    if not isinstance(raw_cameras, list):
        return []

    cameras: list[CameraConfig] = []
    for item in raw_cameras:
        if not isinstance(item, dict):
            continue
        if item.get("enabled") is False:
            continue

        camera_id = str(item.get("id") or "").strip()
        camera_ip = str(item.get("cameraIp") or "").strip()
        if not camera_id or not camera_ip:
            continue

        camera_type = str(item.get("cameraType") or "tapo").strip().lower()
        camera_port = int(item.get("cameraPort") or (8080 if camera_type == "ip_webcam" else 554))
        rtsp_path = str(item.get("rtspPath") or "/stream1")
        rtsp_user = item.get("rtspUser")
        rtsp_password = item.get("rtspPassword")
        rtsp_url = build_rtsp_url(
            camera_type=camera_type,
            camera_ip=camera_ip,
            camera_port=camera_port,
            rtsp_path=rtsp_path,
            rtsp_user=str(rtsp_user).strip() if rtsp_user else None,
            rtsp_password=str(rtsp_password) if rtsp_password else None,
        )

        frame_interval_ms = item.get("frameIntervalMs")
        motion_gate_enabled = item.get("motionGateEnabled")
        cameras.append(
            CameraConfig(
                id=camera_id,
                label=item.get("label"),
                direction=str(item.get("direction") or "entry"),
                enabled=True,
                rtsp_url=rtsp_url,
                frame_interval_ms=int(frame_interval_ms) if frame_interval_ms else None,
                motion_gate_enabled=(
                    bool(motion_gate_enabled) if motion_gate_enabled is not None else None
                ),
            )
        )
    return cameras


def camera_config_fingerprint(cameras: list[CameraConfig]) -> tuple:
    return tuple(
        (
            camera.id,
            camera.direction,
            camera.rtsp_url,
            camera.frame_interval_ms,
            camera.motion_gate_enabled,
        )
        for camera in cameras
    )


class RemoteCameraConfigService:
    """Fetch camera list from CRM/backend on an interval."""

    def __init__(self, agent: AnprAgent) -> None:
        self._agent = agent
        self._task: asyncio.Task | None = None
        self._last_fingerprint: tuple | None = None
        self._last_error: str | None = None
        self._last_updated_at: str | None = None

    def status(self) -> dict:
        settings = self._agent.settings
        cameras = [
            {
                "id": camera.id,
                "label": camera.label or camera.id,
                "direction": camera.direction,
                "streamUrl": mask_stream_url(camera.rtsp_url),
            }
            for camera in settings.cameras
        ]
        return {
            "enabled": settings.remote_camera_config_enabled,
            "refreshSeconds": settings.remote_camera_config_refresh_seconds,
            "cameraCount": len(settings.cameras),
            "cameras": cameras,
            "lastUpdatedAt": self._last_updated_at,
            "lastError": self._last_error,
        }

    def start(self) -> None:
        if not self._agent.settings.remote_camera_config_enabled:
            return
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._poll_loop(), name="remote-camera-config")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    async def refresh_once(self) -> bool:
        settings = self._agent.settings
        if not settings.remote_camera_config_enabled:
            return False

        try:
            payload = await self._agent.backend.fetch_remote_cameras()
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning(
                "remote camera config fetch failed",
                extra={"event": "remote_camera_config_failed", "error": str(exc)},
            )
            return False

        if payload is None:
            self._last_error = "Backend har inte aktiverat fjärrkonfiguration av kameror"
            return False

        cameras = camera_configs_from_remote_payload(payload)
        fingerprint = camera_config_fingerprint(cameras)
        if fingerprint == self._last_fingerprint:
            self._last_error = None
            self._last_updated_at = payload.get("updatedAt")
            return True

        await self._agent.apply_camera_configs(cameras)
        self._last_fingerprint = fingerprint
        self._last_updated_at = payload.get("updatedAt")
        self._last_error = None
        logger.info(
            "remote camera config applied",
            extra={
                "event": "remote_camera_config_applied",
                "camera_ids": [camera.id for camera in cameras],
                "camera_count": len(cameras),
            },
        )
        return True

    async def _poll_loop(self) -> None:
        settings = self._agent.settings
        interval = max(15, settings.remote_camera_config_refresh_seconds)
        await self.refresh_once()
        while True:
            await asyncio.sleep(interval)
            await self.refresh_once()
