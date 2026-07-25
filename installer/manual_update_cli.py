"""One-shot update for agents where the dashboard updater is broken."""

from __future__ import annotations

import argparse
import sys
import uuid

from installer.remote_update_cli import run_remote_update_job
from installer.updater import fetch_backend_agent_version
from installer.updater import _read_installed_backend_url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANPR manual update (recovery)")
    parser.add_argument("--download-url", default=None)
    parser.add_argument("--target-version", default=None)
    args = parser.parse_args(argv)

    download_url = args.download_url
    target_version = args.target_version

    if not download_url or not target_version:
        backend_url = _read_installed_backend_url()
        if not backend_url:
            print("BACKEND_URL saknas i .env", file=sys.stderr)
            return 1
        info = fetch_backend_agent_version(backend_url)
        if not info or not info.get("downloadUrl"):
            print("Kunde inte hamta agent-version fran backend", file=sys.stderr)
            return 1
        target_version = target_version or info["version"]
        download_url = download_url or info["downloadUrl"]

    request_id = f"manual-{uuid.uuid4().hex[:8]}"
    try:
        run_remote_update_job(
            request_id,
            download_url=download_url,
            target_version=target_version,
        )
    except Exception as exc:
        print(f"Uppdatering misslyckades: {exc}", file=sys.stderr)
        return 1

    print(f"Uppdatering klar (version {target_version}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
