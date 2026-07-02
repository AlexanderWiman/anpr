"""Shared agent status snapshot for local dashboard and remote heartbeat."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src import __version__

if TYPE_CHECKING:
    from src.services.agent import AnprAgent


def _camera_status(pipeline) -> dict:
    camera = pipeline.capture
    return {
        "id": pipeline.camera_id,
        "label": pipeline.label,
        "direction": pipeline.direction,
        "source": camera.source_type,
        "status": camera.status.value,
        "lastFrameAt": (
            camera.last_frame_at.isoformat() if camera.last_frame_at else None
        ),
        "framesCaptured": camera.frames_captured,
    }


def build_status_report(agent: "AnprAgent", process_started_at: datetime) -> dict:
    from src.config.settings import settings_env_path

    settings = agent.settings
    config_path = settings_env_path()
    now = datetime.now(timezone.utc)
    agent_status = agent.controller.status()
    primary = agent.primary_pipeline.capture
    delivery = agent.delivery
    cameras = [_camera_status(pipeline) for pipeline in agent.pipelines.values()]

    return {
        "status": "ok",
        "version": __version__,
        "reportedAt": now.isoformat(),
        "agent": agent_status,
        "site": {
            "siteId": settings.site_id,
            "cameraId": settings.camera_id,
            "direction": settings.direction,
            "cameraCount": len(cameras),
        },
        "camera": {
            "source": primary.source_type,
            "status": primary.status.value,
            "lastFrameAt": (
                primary.last_frame_at.isoformat() if primary.last_frame_at else None
            ),
            "framesCaptured": primary.frames_captured,
        },
        "cameras": cameras,
        "anpr": {
            "provider": agent.provider_name,
            "minConfidence": settings.min_confidence,
            "cooldownSeconds": settings.plate_cooldown_seconds,
            "ocrProcessing": agent._ocr_busy,
            "pendingFrames": len(agent._ocr_queue),
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
