"""Dashboard-triggered agent updates."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def local_update_state_path() -> Path:
    from installer.engine import support_dir

    return support_dir() / "local-update.json"


def read_local_update_state() -> dict | None:
    path = local_update_state_path()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    status = payload.get("status")
    if status not in {"running", "completed", "failed"}:
        return None
    return payload


def build_update_status_payload() -> dict:
    from src import __version__
    from installer.engine import install_dir, is_installed, read_version
    from installer.updater import display_version, remote_update_status

    if not is_installed():
        return {
            "installed": False,
            "currentVersion": __version__,
            "updateAvailable": False,
            "job": read_local_update_state(),
        }

    current = read_version(install_dir())
    remote = remote_update_status(current)
    remote_version = display_version(
        remote.get("remoteVersion"),
        fallback=remote.get("githubVersion") or remote.get("backendVersion"),
    )
    update_available = bool(remote.get("remoteUpdateAvailable"))
    if current and remote_version and not _is_newer(remote_version, current):
        update_available = False

    job = read_local_update_state()
    if job and job.get("status") == "running":
        update_available = False

    return {
        "installed": True,
        "currentVersion": current,
        "remoteVersion": remote_version,
        "updateAvailable": update_available,
        "updateSource": remote.get("updateSource"),
        "job": job,
    }


def _is_newer(remote: str | None, current: str | None) -> bool:
    from installer.updater import is_newer

    return is_newer(remote, current)


def spawn_local_update() -> None:
    job = read_local_update_state()
    if job and job.get("status") == "running":
        raise RuntimeError("Uppdatering pågår redan")

    from installer.engine import install_dir

    app_dir = install_dir()
    python = _python_executable(app_dir)
    args = [python, "-m", "installer.local_update_cli"]

    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

    logger.info("starting local dashboard update", extra={"event": "local_update_spawn"})
    subprocess.Popen(
        args,
        cwd=str(app_dir),
        creationflags=creationflags,
        close_fds=True,
    )


def _python_executable(app_dir: Path) -> str:
    if sys.platform == "win32":
        candidate = app_dir / ".venv" / "Scripts" / "python.exe"
        if candidate.is_file():
            return str(candidate)
    else:
        candidate = app_dir / ".venv" / "bin" / "python"
        if candidate.is_file():
            return str(candidate)
    return sys.executable
