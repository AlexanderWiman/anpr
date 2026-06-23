from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from src import __version__

if TYPE_CHECKING:
    from src.services.agent import AnprAgent

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"


def create_web_app(agent: "AnprAgent", process_started_at: datetime) -> FastAPI:
    settings = agent.settings
    app = FastAPI(title="ANPR Edge Agent", version=__version__)

    def build_status() -> dict:
        now = datetime.now(timezone.utc)
        agent_status = agent.controller.status()
        camera = agent.camera
        delivery = agent.delivery

        return {
            "status": "ok",
            "agent": agent_status,
            "site": {
                "siteId": settings.site_id,
                "cameraId": settings.camera_id,
                "direction": settings.direction,
            },
            "camera": {
                "source": camera.source_type,
                "status": camera.status.value,
                "lastFrameAt": (
                    camera.last_frame_at.isoformat() if camera.last_frame_at else None
                ),
                "framesCaptured": camera.frames_captured,
            },
            "anpr": {
                "provider": agent.provider_name,
                "minConfidence": settings.min_confidence,
                "cooldownSeconds": settings.plate_cooldown_seconds,
                "ocrProcessing": agent._ocr_busy,
                "pendingFrames": 1 if agent._pending_frame else 0,
            },
            "backend": {
                "url": settings.backend_url,
                "tokenHint": settings.anpr_agent_token[-4:] if len(settings.anpr_agent_token) >= 4 else "????",
                **delivery.backend_status.as_dict(),
            },
            "bookingHints": agent.booking_hints.status(),
            "queue": {
                "size": delivery.queue_size,
                **delivery.stats,
            },
            "lastDetection": agent.deduplicator.last_detection,
            "uptimeSeconds": round((now - process_started_at).total_seconds(), 1),
        }

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
        return HTMLResponse("<h1>ANPR Edge Agent</h1><p>Dashboard missing.</p>")

    @app.get("/health")
    async def health():
        return build_status()

    @app.get("/api/status")
    async def api_status():
        await agent.delivery.refresh_backend_status()
        return build_status()

    @app.get("/api/agent/status")
    async def api_agent_status():
        return agent.controller.status()

    @app.post("/api/agent/start")
    async def api_agent_start():
        result = await agent.controller.start()
        if not result["ok"]:
            raise HTTPException(status_code=409, detail=result["message"])
        return result

    @app.post("/api/agent/stop")
    async def api_agent_stop():
        result = await agent.controller.stop()
        if not result["ok"]:
            raise HTTPException(status_code=409, detail=result["message"])
        return result

    @app.get("/api/events")
    async def api_events(limit: int = 50):
        return {"events": agent.history.list_recent(limit=limit)}

    @app.get("/api/queue")
    async def api_queue():
        pending = []
        for item in agent.queue.all_events():
            pending.append(
                {
                    "id": item.id,
                    "plate": item.event.plate,
                    "confidence": item.event.confidence,
                    "attempts": item.attempts,
                    "lastError": item.last_error,
                    "nextRetryAt": (
                        item.next_retry_at.isoformat() if item.next_retry_at else None
                    ),
                    "createdAt": item.created_at.isoformat(),
                }
            )
        return {"queue": pending, "size": len(pending)}

    @app.post("/api/backend/ping")
    async def api_backend_ping():
        status = await agent.delivery.refresh_backend_status()
        return status.as_dict()

    return app
