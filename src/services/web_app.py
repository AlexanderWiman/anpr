from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from src import __version__
from src.services.status_report import build_status_report

if TYPE_CHECKING:
    from src.services.agent import AnprAgent

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"


def _dashboard_html() -> HTMLResponse:
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        return HTMLResponse("<h1>ANPR Edge Agent</h1><p>Dashboard missing.</p>")
    html = index.read_text(encoding="utf-8")
    html = html.replace('id="agent-version">v…</span>', f'id="agent-version">v{__version__}</span>')
    return HTMLResponse(html)


def create_web_app(agent: "AnprAgent", process_started_at: datetime) -> FastAPI:
    app = FastAPI(title="ANPR Edge Agent", version=__version__)

    def build_status() -> dict:
        return build_status_report(agent, process_started_at)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _dashboard_html()

    @app.get("/api/version")
    async def api_version():
        return {"version": __version__}

    @app.get("/health")
    async def health():
        return build_status()

    @app.get("/api/status")
    async def api_status():
        await agent.delivery.refresh_backend_status(max_age_seconds=30)
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
        status = await agent.delivery.refresh_backend_status(force=True)
        return status.as_dict()

    @app.get("/api/logs")
    async def api_logs(
        tail: int = 200,
        level: str | None = None,
        source: str = "all",
        q: str | None = None,
    ):
        from src.utils.log_reader import read_recent_logs

        if source not in {"agent", "startup", "all"}:
            raise HTTPException(status_code=400, detail="source must be agent, startup, or all")
        if level is not None and level.lower() not in {"info", "warning", "error"}:
            raise HTTPException(status_code=400, detail="level must be info, warning, or error")
        return read_recent_logs(
            agent.settings.log_dir,
            tail=tail,
            min_level=level,
            source=source,
            query=q,
        )

    @app.post("/api/logs/export")
    async def api_logs_export(hours: float | None = None):
        """Bundle last N hours of logs and upload to backend (manual IT trigger)."""
        from src.utils.log_export import build_log_export

        export_hours = float(hours) if hours is not None else agent.settings.log_export_hours
        try:
            bundle = await asyncio.to_thread(
                build_log_export,
                agent.settings.log_dir,
                hours=export_hours,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Kunde inte läsa loggar: {exc}") from exc

        import uuid

        request_id = str(uuid.uuid4())
        try:
            await agent.backend.upload_log_export(
                request_id,
                status="completed",
                hours=bundle.hours,
                line_count=bundle.line_count,
                exported_at=bundle.exported_at,
                truncated=bundle.truncated,
                original_bytes=bundle.original_bytes,
                compressed_bytes=bundle.compressed_bytes,
                content_gzip_base64=bundle.content_gzip_base64,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Kunde inte skicka loggar till backend: {exc}",
            ) from exc

        return {
            "ok": True,
            "requestId": request_id,
            "hours": bundle.hours,
            "lineCount": bundle.line_count,
            "truncated": bundle.truncated,
            "compressedBytes": bundle.compressed_bytes,
        }

    @app.get("/api/update/status")
    async def api_update_status():
        from src.services.local_update import build_update_status_payload

        return await asyncio.to_thread(build_update_status_payload)

    @app.post("/api/update/start")
    async def api_update_start():
        from src.services.local_update import build_update_status_payload, spawn_local_update

        status = await asyncio.to_thread(build_update_status_payload)
        job = status.get("job") or {}
        if job.get("status") == "running":
            raise HTTPException(status_code=409, detail="Uppdatering pågår redan")
        if not status.get("updateAvailable"):
            raise HTTPException(status_code=400, detail="Ingen ny version tillgänglig")

        try:
            await asyncio.to_thread(spawn_local_update)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Kunde inte starta uppdatering: {exc}") from exc

        return {"ok": True, "message": "Uppdatering startad — sidan kan tappa kontakten en stund."}

    return app
