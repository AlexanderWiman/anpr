"""Handle IT-triggered remote updates delivered via heartbeat commands."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def update_result_path() -> Path:
    from installer.engine import support_dir

    return support_dir() / "update-result.json"


def load_pending_update_result() -> dict | None:
    path = update_result_path()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    request_id = payload.get("requestId")
    status = payload.get("status")
    if not request_id or status not in {"in_progress", "completed", "failed"}:
        return None
    return {
        "requestId": str(request_id),
        "status": status,
        "error": payload.get("error"),
        "newVersion": payload.get("newVersion"),
    }


def clear_update_result() -> None:
    path = update_result_path()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _python_executable() -> str:
    from installer.engine import install_dir

    app_dir = install_dir()
    if sys.platform == "win32":
        candidate = app_dir / ".venv" / "Scripts" / "python.exe"
        if candidate.is_file():
            return str(candidate)
    else:
        candidate = app_dir / ".venv" / "bin" / "python"
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def spawn_remote_update(command: dict) -> None:
    request_id = command.get("requestId")
    if not request_id:
        logger.warning("remote update command missing requestId")
        return

    from installer.engine import install_dir

    app_dir = install_dir()
    args = [
        _python_executable(),
        "-m",
        "installer.remote_update_cli",
        "--request-id",
        str(request_id),
    ]
    download_url = command.get("downloadUrl")
    if isinstance(download_url, str) and download_url.strip():
        args.extend(["--download-url", download_url.strip()])
    target_version = command.get("version")
    if isinstance(target_version, str) and target_version.strip():
        args.extend(["--target-version", target_version.strip()])

    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

    logger.info(
        "starting remote update",
        extra={"event": "remote_update_spawn", "request_id": request_id},
    )
    subprocess.Popen(
        args,
        cwd=str(app_dir),
        creationflags=creationflags,
        close_fds=True,
    )


def handle_heartbeat_commands(commands: list[dict] | None) -> None:
    if not commands:
        return

    for command in commands:
        if command.get("type") != "update":
            continue
        spawn_remote_update(command)
        return
