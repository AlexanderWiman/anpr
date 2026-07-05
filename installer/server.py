"""Local web server for the ANPR install wizard."""

from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from installer.engine import (
    InstallConfig,
    install_status_payload,
    run_install,
    run_update,
)
from installer.updater import run_remote_update
from installer.prerequisites import (
    install_all_missing,
    install_prerequisite,
    prerequisite_status_payload,
)
from installer.sites import DEFAULT_BACKEND_URL, SITE_PROFILES

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="ANPR Installer", docs_url=None, redoc_url=None)

_state = {
    "status": "idle",  # idle | running | done | error
    "message": "",
    "error": None,
    "prereq_status": "idle",
    "prereq_message": "",
    "prereq_result": None,
}
_lock = threading.Lock()


class InstallCameraRequest(BaseModel):
    camera_id: str = "hall-1"
    label: str = "Hall 1"
    direction: str = "entry"
    camera_ip: str
    camera_type: str = "tapo"
    camera_port: int = 554
    rtsp_path: str = "/stream1"
    rtsp_user: str = ""
    rtsp_password: str = ""


class InstallRequest(BaseModel):
    site_id: str
    hall_count: int = 1
    cameras: list[InstallCameraRequest] = Field(default_factory=list)
    remote_camera_config_enabled: bool = False
    backend_url: str = DEFAULT_BACKEND_URL
    anpr_token: str = Field(min_length=8)


class ValidateCredentialsRequest(BaseModel):
    site_id: str
    backend_url: str = DEFAULT_BACKEND_URL
    anpr_token: str = Field(min_length=8)


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/waiting.html")
async def waiting_html():
    """Bootstrap opens this path; redirect once the real wizard server is up."""
    return RedirectResponse(url="/", status_code=302)


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/api/ping")
async def api_ping():
    return {"ok": True}


@app.get("/api/sites")
async def api_sites():
    return {
        "sites": [
            {
                "id": site.id,
                "label": site.label,
                "defaultHalls": site.default_halls,
                "maxHalls": site.max_halls,
            }
            for site in SITE_PROFILES
        ],
        "defaultBackendUrl": DEFAULT_BACKEND_URL,
    }


@app.get("/api/check")
async def api_check():
    payload = prerequisite_status_payload()
    return payload


@app.post("/api/prerequisites/install/{item_id}")
async def api_install_prerequisite(item_id: str):
    with _lock:
        if _state.get("prereq_status") == "running":
            raise HTTPException(409, "Installation pågår redan")

    result_holder: dict = {}

    def work() -> None:
        def log(msg: str) -> None:
            with _lock:
                _state["prereq_message"] = msg

        with _lock:
            _state["prereq_status"] = "running"
            _state["prereq_message"] = "Startar..."

        try:
            result = install_prerequisite(item_id, log)
            result_holder.update(result)
            with _lock:
                _state["prereq_status"] = "done"
                _state["prereq_message"] = result.get("message", "")
                _state["prereq_result"] = result
        except Exception as exc:
            with _lock:
                _state["prereq_status"] = "error"
                _state["prereq_message"] = str(exc)
                _state["prereq_result"] = {"ok": False, "message": str(exc)}

    threading.Thread(target=work, daemon=True).start()
    return {"started": True}


@app.post("/api/prerequisites/install-all")
async def api_install_all_prerequisites():
    with _lock:
        if _state.get("prereq_status") == "running":
            raise HTTPException(409, "Installation pågår redan")

    def work() -> None:
        def log(msg: str) -> None:
            with _lock:
                _state["prereq_message"] = msg

        with _lock:
            _state["prereq_status"] = "running"
            _state["prereq_message"] = "Startar..."

        try:
            result = install_all_missing(log)
            with _lock:
                _state["prereq_status"] = "done"
                _state["prereq_message"] = "Klart"
                _state["prereq_result"] = result
        except Exception as exc:
            with _lock:
                _state["prereq_status"] = "error"
                _state["prereq_message"] = str(exc)
                _state["prereq_result"] = {"ok": False, "message": str(exc)}

    threading.Thread(target=work, daemon=True).start()
    return {"started": True}


@app.get("/api/prerequisites/status")
async def api_prerequisites_job_status():
    with _lock:
        return {
            "status": _state.get("prereq_status", "idle"),
            "message": _state.get("prereq_message", ""),
            "result": _state.get("prereq_result"),
            "check": prerequisite_status_payload(),
        }


@app.get("/api/install/existing")
async def api_install_existing():
    return install_status_payload()


@app.post("/api/install/validate-credentials")
async def api_validate_credentials(body: ValidateCredentialsRequest):
    from installer.token_check import validate_backend_credentials

    ok, message = validate_backend_credentials(
        site_id=body.site_id,
        backend_url=body.backend_url.rstrip("/"),
        token=body.anpr_token,
    )
    return {"ok": ok, "message": message}


@app.get("/api/install/status")
async def api_install_status():
    with _lock:
        return dict(_state)


@app.post("/api/install")
async def api_install(body: InstallRequest):
    with _lock:
        if _state["status"] == "running":
            raise HTTPException(409, "Installation pågår redan")

    from installer.engine import InstallCameraConfig

    if not body.remote_camera_config_enabled and not body.cameras:
        raise HTTPException(400, "Minst en kamera krävs om IT inte konfigurerar kameror senare")

    cameras = []
    if not body.remote_camera_config_enabled:
        cameras = [
            InstallCameraConfig(
                camera_id=camera.camera_id,
                label=camera.label,
                direction=camera.direction,
                camera_ip=camera.camera_ip,
                camera_type=camera.camera_type,
                camera_port=camera.camera_port,
                rtsp_path=camera.rtsp_path,
                rtsp_user=camera.rtsp_user,
                rtsp_password=camera.rtsp_password,
            )
            for camera in body.cameras
        ]
    cfg = InstallConfig(
        site_id=body.site_id,
        backend_url=body.backend_url.rstrip("/"),
        anpr_token=body.anpr_token,
        remote_camera_config_enabled=body.remote_camera_config_enabled,
        cameras=cameras,
    )

    def work() -> None:
        def log(msg: str) -> None:
            with _lock:
                _state["message"] = msg

        with _lock:
            _state["status"] = "running"
            _state["message"] = "Startar..."
            _state["error"] = None

        try:
            run_install(cfg, log, open_browser=False)
            with _lock:
                _state["status"] = "done"
                _state["message"] = "Installation klar"
        except Exception as exc:
            with _lock:
                _state["status"] = "error"
                _state["error"] = str(exc)
                _state["message"] = "Installation misslyckades"

    threading.Thread(target=work, daemon=True).start()
    return {"started": True}


@app.post("/api/update/remote")
async def api_update_remote():
    with _lock:
        if _state["status"] == "running":
            raise HTTPException(409, "Uppdatering pågår redan")
        if not install_status_payload()["installed"]:
            raise HTTPException(400, "ANPR är inte installerat på den här datorn")

    def work() -> None:
        def log(msg: str) -> None:
            with _lock:
                _state["message"] = msg

        with _lock:
            _state["status"] = "running"
            _state["message"] = "Hämtar uppdatering…"
            _state["error"] = None
            _state["mode"] = "update"

        try:
            run_remote_update(log)
            with _lock:
                _state["status"] = "done"
                _state["message"] = "Uppdatering klar"
        except Exception as exc:
            with _lock:
                _state["status"] = "error"
                _state["error"] = str(exc)
                _state["message"] = "Uppdatering misslyckades"

    threading.Thread(target=work, daemon=True).start()
    return {"started": True}


@app.post("/api/update")
async def api_update():
    with _lock:
        if _state["status"] == "running":
            raise HTTPException(409, "Uppdatering pågår redan")
        if not install_status_payload()["installed"]:
            raise HTTPException(400, "ANPR är inte installerat på den här datorn")

    def work() -> None:
        def log(msg: str) -> None:
            with _lock:
                _state["message"] = msg

        with _lock:
            _state["status"] = "running"
            _state["message"] = "Startar uppdatering..."
            _state["error"] = None
            _state["mode"] = "update"

        try:
            run_update(log, open_browser=False)
            with _lock:
                _state["status"] = "done"
                _state["message"] = "Uppdatering klar"
        except Exception as exc:
            with _lock:
                _state["status"] = "error"
                _state["error"] = str(exc)
                _state["message"] = "Uppdatering misslyckades"

    threading.Thread(target=work, daemon=True).start()
    return {"started": True}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _open_browser(url: str) -> None:
    import os
    import subprocess
    import sys
    import webbrowser

    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
        return
    if os.environ.get("ANPR_INSTALLER_OPEN") == "open":
        subprocess.run(["open", url], check=False)
        return
    webbrowser.open(url)


def run_server(host: str = "127.0.0.1", port: int = 17880) -> None:
    import uvicorn

    url = f"http://{host}:{port}"
    threading.Timer(0.5, lambda: _open_browser(url)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
