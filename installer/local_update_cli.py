"""Run a dashboard-triggered update in a separate process."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone


def _state_path():
    from installer.engine import support_dir

    return support_dir() / "local-update.json"


def _log_path():
    from installer.engine import support_dir

    path = support_dir() / "logs" / "local-update.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_state(
    status: str,
    *,
    message: str | None = None,
    error: str | None = None,
    new_version: str | None = None,
) -> None:
    path = _state_path()
    existing: dict = {}
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                existing = payload
        except (OSError, json.JSONDecodeError):
            existing = {}

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        **existing,
        "status": status,
        "message": message,
        "error": error,
        "newVersion": new_version,
        "updatedAt": now,
    }
    if status == "running" and "startedAt" not in existing:
        payload["startedAt"] = now
    if status in {"completed", "failed"}:
        payload["completedAt"] = now

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_log(message: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with _log_path().open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")


def run_local_update_job() -> None:
    from installer.engine import install_dir, read_version, start_agent
    from installer.updater import run_remote_update

    def log(message: str) -> None:
        _append_log(message)
        _write_state("running", message=message)

    _write_state("running", message="Startar uppdatering…")
    try:
        run_remote_update(log)
        new_version = read_version(install_dir())
        _write_state(
            "completed",
            message=f"Uppdatering klar (version {new_version or 'okänd'}).",
            new_version=new_version,
        )
    except Exception as exc:
        _append_log(f"Uppdatering misslyckades: {exc}")
        _append_log(traceback.format_exc())
        new_version = None
        try:
            from installer.engine import read_version

            new_version = read_version(install_dir())
            start_agent(install_dir(), _append_log)
        except Exception:
            pass
        _write_state(
            "failed",
            message="Uppdatering misslyckades",
            error=str(exc),
            new_version=new_version,
        )
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANPR local dashboard update")
    parser.parse_args(argv)
    try:
        run_local_update_job()
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
