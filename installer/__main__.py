"""Start the ANPR install wizard in your browser."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time

from installer.bootstrap import start_waiting_server, wait_until_listening
from installer.runtime import ensure_installer_venv

DEFAULT_PORT = 17880


def _log(msg: str) -> None:
    print(msg, flush=True)


def _resolve_port() -> int:
    preferred = int(os.environ.get("ANPR_INSTALLER_PORT", str(DEFAULT_PORT)))
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", preferred))
        return preferred
    except OSError:
        try:
            with socket.create_connection(("127.0.0.1", preferred), timeout=0.3):
                _log(f"En installationsguide körs redan på port {preferred}.")
                _log("Stäng det svarta Installer CMD-fönstret och kör Installer.cmd igen.")
                _open_url(f"http://127.0.0.1:{preferred}")
                sys.exit(1)
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _open_url(url: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
        return
    if os.environ.get("ANPR_INSTALLER_OPEN") == "open":
        subprocess.run(["open", url], check=False)
        return
    import webbrowser

    webbrowser.open(url)


def _server_running(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def _wait_for_existing_server(port: int) -> None:
    """Keep launcher alive while an installer instance is already running."""
    _log("Guiden körs redan — håller appen öppen tills du stänger guiden.")
    while _server_running(port):
        time.sleep(1)


def _wait_for_server(port: int, attempts: int = 100) -> bool:
    for _ in range(attempts):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _wait_for_api_ready(port: int, attempts: int = 150) -> bool:
    import urllib.error
    import urllib.request

    ping_url = f"http://127.0.0.1:{port}/api/ping"
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(ping_url, timeout=0.3) as response:
                if response.status == 200:
                    return True
        except urllib.error.HTTPError as exc:
            if exc.code == 503:
                pass
        except OSError:
            pass
        time.sleep(0.1)
    return False


def main() -> None:
    ensure_installer_venv(_log)

    port = _resolve_port()
    url = f"http://127.0.0.1:{port}"
    waiting_url = f"{url}/waiting.html?port={port}"

    bootstrap_httpd, _bootstrap_thread = start_waiting_server(port)
    if not wait_until_listening(port):
        _log("Kunde inte starta väntesida.")
        sys.exit(1)

    _open_url(waiting_url)
    _log("Väntesida öppnad — laddar installationsguiden...")

    try:
        import uvicorn
        from installer.server import app
    except ImportError as exc:
        bootstrap_httpd.shutdown()
        _log(f"Installer dependencies missing: {exc}")
        _log("Run: pip install -r requirements.txt")
        sys.exit(1)

    bootstrap_httpd.shutdown()
    bootstrap_httpd.server_close()
    time.sleep(0.2)

    def serve() -> None:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    if not _wait_for_server(port):
        _log("Server startade inte.")
        sys.exit(1)

    if _wait_for_api_ready(port):
        _open_url(url)
    else:
        _log("Guiden svarar inte ännu — öppna manuellt:")
        _log(f"  {url}")

    _log("")
    _log("  ANPR Install Wizard")
    _log(f"  {url}")
    _log("  Stäng detta fönster när installationen är klar.")
    _log("")

    try:
        thread.join()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
