"""Shared agent status snapshot for local dashboard and remote heartbeat."""

import platform
import socket
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src import __version__

if TYPE_CHECKING:
    from src.services.agent import AnprAgent


from src.utils.rtsp_url import mask_stream_url

# Show "connected" in UI while agent is running if we got a frame recently,
# even during brief RTSP reconnects (dashboard polling must not imply camera health).
RECENT_FRAME_GRACE_SECONDS = 120.0


def _host_info() -> dict:
    try:
        hostname = socket.gethostname().strip() or None
    except OSError:
        hostname = None
    return {
        "hostname": hostname,
        "platform": platform.system() or None,
    }


def effective_camera_status(
    raw_status: str,
    last_frame_at: datetime | None,
    *,
    agent_running: bool,
    now: datetime,
) -> str:
    if not agent_running:
        return "idle"
    if raw_status == "connected":
        return "connected"
    if last_frame_at is not None:
        age = (now - last_frame_at).total_seconds()
        if age <= RECENT_FRAME_GRACE_SECONDS:
            return "connected"
    return raw_status


def _camera_status(pipeline, *, agent_running: bool, now: datetime) -> dict:
    camera = pipeline.capture
    status_message = getattr(camera, "status_message", None)
    last_frame_at = camera.last_frame_at
    raw_status = camera.status.value
    effective = effective_camera_status(
        raw_status,
        last_frame_at,
        agent_running=agent_running,
        now=now,
    )
    last_frame_age = (
        round((now - last_frame_at).total_seconds(), 1) if last_frame_at else None
    )
    return {
        "id": pipeline.camera_id,
        "label": pipeline.label,
        "direction": pipeline.direction,
        "source": camera.source_type,
        "status": raw_status,
        "effectiveStatus": effective,
        "statusMessage": status_message,
        "streamUrl": mask_stream_url(pipeline.config.rtsp_url),
        "lastFrameAt": last_frame_at.isoformat() if last_frame_at else None,
        "lastFrameAgeSeconds": last_frame_age,
        "framesCaptured": camera.frames_captured,
    }


def build_status_report(agent: "AnprAgent", process_started_at: datetime) -> dict:
    from src.config.settings import settings_env_path

    settings = agent.settings
    config_path = settings_env_path()
    now = datetime.now(timezone.utc)
    agent_status = agent.controller.status()
    agent_running = agent_status.get("state") == "running"
    delivery = agent.delivery
    cameras = [
        _camera_status(pipeline, agent_running=agent_running, now=now)
        for pipeline in agent.pipelines.values()
    ]
    primary = agent.primary_pipeline
    primary_capture = primary.capture if primary is not None else None

    return {
        "status": "ok",
        "version": __version__,
        "reportedAt": now.isoformat(),
        "host": _host_info(),
        "agent": agent_status,
        "site": {
            "siteId": settings.site_id,
            "cameraId": settings.camera_id,
            "direction": settings.direction,
            "cameraCount": len(cameras),
        },
        "camera": {
            "source": primary_capture.source_type if primary_capture else "none",
            "status": primary_capture.status.value if primary_capture else "unconfigured",
            "statusMessage": (
                primary_capture.status_message
                if primary_capture and hasattr(primary_capture, "status_message")
                else None
            ),
            "lastFrameAt": (
                primary_capture.last_frame_at.isoformat()
                if primary_capture and primary_capture.last_frame_at
                else None
            ),
            "framesCaptured": primary_capture.frames_captured if primary_capture else 0,
        },
        "cameras": cameras,
        "remoteCameraConfig": agent.remote_camera_config.status(),
        "anpr": {
            "provider": agent.provider_name,
            "minConfidence": settings.min_confidence,
            "cooldownSeconds": settings.plate_cooldown_seconds,
            "ocrProcessing": agent._ocr_busy,
            "pendingFrames": len(agent._ocr_queue),
            "ready": agent._ocr_last_error is None,
            "lastError": agent._ocr_last_error,
            "lastErrorAt": (
                agent._ocr_last_error_at.isoformat()
                if agent._ocr_last_error_at
                else None
            ),
        },
        "backend": {
            "url": settings.backend_url,
            "tokenHint": (
                settings.anpr_agent_token[-4:]
                if len(settings.anpr_agent_token) >= 4
                else "????"
            ),
            "configPath": config_path,
            **delivery.backend_status.as_dict(),
        },
        "bookingHints": agent.booking_hints.status(),
        "heartbeat": agent.heartbeat.status(),
        "queue": {
            "size": delivery.queue_size,
            **delivery.stats,
        },
        "lastDetection": agent.deduplicator.last_detection,
        "uptimeSeconds": round((now - process_started_at).total_seconds(), 1),
    }
