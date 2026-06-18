"""Start the ANPR install wizard in your browser."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time

from installer.bootstrap import start_waiting_server, wait_until_listening

DEFAULT_PORT = 17880
_INSTALLER_DEPS = (
    "fastapi",
    "uvicorn",
    "httpx",
    "pydantic",
    "pydantic-settings",
    "python-dotenv",
)


def _log(msg: str) -> None:
    print(msg, flush=True)


def _ensure_installer_deps() -> None:
    try:
        import uvicorn  # noqa: F401
        from installer.server import app  # noqa: F401
    except ImportError:
        _log("Installerar Python-komponenter (första gången kan ta några minuter)...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", *_INSTALLER_DEPS],
            check=True,
        )


def _resolve_port() -> tuple[int, bool]:
    """Return (port, reuse_existing_server)."""
    preferred = int(os.environ.get("ANPR_INSTALLER_PORT", str(DEFAULT_PORT)))
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", preferred))
        return preferred, False
    except OSError:
        try:
            with socket.create_connection(("127.0.0.1", preferred), timeout=0.3):
                _log(f"Installationsguiden körs redan på port {preferred}.")
                return preferred, True
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1], False


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


def main() -> None:
    port, reuse = _resolve_port()
    url = f"http://127.0.0.1:{port}"
    waiting_url = f"{url}/waiting.html?port={port}"

    if reuse:
        _open_url(url)
        _log(f"\n  ANPR Install Wizard (redan igång)\n  {url}\n")
        _wait_for_existing_server(port)
        return

    bootstrap_httpd, _bootstrap_thread = start_waiting_server(port)
    if not wait_until_listening(port):
        _log("Kunde inte starta väntesida.")
        sys.exit(1)

    _open_url(waiting_url)
    _log("Väntesida öppnad — laddar installationsguiden...")

    _ensure_installer_deps()

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
