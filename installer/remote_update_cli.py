"""Run a backend-triggered remote update in a separate process."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


def _result_path() -> Path:
    from installer.engine import support_dir

    return support_dir() / "update-result.json"


def _log_path() -> Path:
    from installer.engine import support_dir

    path = support_dir() / "logs" / "remote-update.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_result(
    request_id: str,
    status: str,
    *,
    error: str | None = None,
    new_version: str | None = None,
) -> None:
    payload = {
        "requestId": request_id,
        "status": status,
        "error": error,
        "newVersion": new_version,
        "writtenAt": datetime.now(timezone.utc).isoformat(),
    }
    path = _result_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_log(message: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{stamp}] {message}\n"
    path = _log_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def run_remote_update_job(
    request_id: str,
    *,
    download_url: str | None = None,
    target_version: str | None = None,
) -> None:
    from installer.engine import install_dir, read_version, start_agent, stop_agent
    from installer.updater import download_release_source, run_remote_update

    app_dir = install_dir()

    def log(message: str) -> None:
        _append_log(message)

    _write_result(request_id, "in_progress")
    stop_agent(app_dir, log)

    if download_url:
        staging = download_release_source(log, download_url=download_url)
        from installer.engine import (
            copy_application,
            create_dashboard_shortcut,
            install_autostart,
            setup_python_env,
        )

        try:
            log("Installerar fjärrstyrd version…")
            copy_application(staging, app_dir, log)
            log("Uppdaterar Python-paket…")
            setup_python_env(app_dir, log)
            install_autostart(app_dir, log)
            create_dashboard_shortcut(log)
            start_agent(app_dir, log)
            remote = target_version or read_version(app_dir) or "ny"
            log(f"Fjärruppdatering klar (version {remote}).")
            _write_result(request_id, "completed", new_version=read_version(app_dir))
        finally:
            import shutil

            shutil.rmtree(staging, ignore_errors=True)
        return

    run_remote_update(log)
    _write_result(request_id, "completed", new_version=read_version(app_dir))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANPR remote update (IT push)")
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--download-url", default=None)
    parser.add_argument("--target-version", default=None)
    args = parser.parse_args(argv)

    try:
        run_remote_update_job(
            args.request_id,
            download_url=args.download_url,
            target_version=args.target_version,
        )
        return 0
    except Exception as exc:
        _append_log(f"Fjärruppdatering misslyckades: {exc}")
        _append_log(traceback.format_exc())
        new_version = None
        try:
            from installer.engine import install_dir, read_version, start_agent

            new_version = read_version(install_dir())
            start_agent(install_dir(), _append_log)
        except Exception:
            pass
        _write_result(args.request_id, "failed", error=str(exc), new_version=new_version)
        return 1


if __name__ == "__main__":
    sys.exit(main())
