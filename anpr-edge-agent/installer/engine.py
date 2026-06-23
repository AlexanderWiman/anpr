"""Cross-platform install engine for ANPR edge agent."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlparse


@dataclass
class InstallConfig:
    site_id: str
    camera_ip: str
    camera_type: str  # tapo | ip_webcam | rtsp
    camera_port: int
    rtsp_path: str
    rtsp_user: str
    rtsp_password: str
    camera_id: str
    direction: str
    backend_url: str
    anpr_token: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def install_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ["LOCALAPPDATA"]) / "anpr-edge-agent"
    return Path.home() / "Applications" / "anpr-edge-agent"


def support_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ["LOCALAPPDATA"]) / "anpr-edge-agent" / "data"
    return Path.home() / "Library" / "Application Support" / "anpr-edge-agent"


def build_camera_url(cfg: InstallConfig) -> str:
    ip = cfg.camera_ip.strip()
    if cfg.camera_type == "ip_webcam":
        port = cfg.camera_port or 8080
        return f"http://{ip}:{port}/videofeed"

    port = cfg.camera_port or 554
    if cfg.camera_type == "tapo":
        path = "/stream1"
    else:
        path = (cfg.rtsp_path or "/stream1").strip()
    if not path.startswith("/"):
        path = f"/{path}"
    if cfg.rtsp_user:
        user = quote(cfg.rtsp_user, safe="")
        password = quote(cfg.rtsp_password or "", safe="")
        auth = f"{user}:{password}@" if cfg.rtsp_password else f"{user}@"
        return f"rtsp://{auth}{ip}:{port}{path}"
    return f"rtsp://{ip}:{port}{path}"


def parse_env_text(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def decode_camera_url(url: str) -> dict[str, str | int]:
    parsed = urlparse(url)
    if parsed.scheme == "http":
        return {
            "camera_type": "ip_webcam",
            "camera_ip": parsed.hostname or "",
            "camera_port": parsed.port or 8080,
            "rtsp_path": parsed.path or "/videofeed",
            "rtsp_user": "",
            "rtsp_password": "",
        }

    path = parsed.path or "/stream1"
    user = unquote(parsed.username) if parsed.username else ""
    password = unquote(parsed.password) if parsed.password else ""
    camera_type = "tapo" if path == "/stream1" else "rtsp"

    return {
        "camera_type": camera_type,
        "camera_ip": parsed.hostname or "",
        "camera_port": parsed.port or 554,
        "rtsp_path": path,
        "rtsp_user": user,
        "rtsp_password": password,
    }


def read_installed_config() -> dict | None:
    env_path = support_dir() / ".env"
    if not env_path.is_file():
        return None

    env = parse_env_text(env_path.read_text(encoding="utf-8"))
    camera_url = env.get("CAMERA_RTSP_URL", "")
    if not camera_url:
        return None

    camera = decode_camera_url(camera_url)
    return {
        "site_id": env.get("SITE_ID", ""),
        "camera_id": env.get("CAMERA_ID", "entrance-1"),
        "direction": env.get("DIRECTION", "entry"),
        "backend_url": env.get("BACKEND_URL", ""),
        "anpr_token": env.get("ANPR_AGENT_TOKEN", ""),
        **camera,
    }


def render_env(cfg: InstallConfig) -> str:
    def env_value(value: str) -> str:
        if any(ch in value for ch in (' ', '=', '#', '"', "'")):
            return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        return value

    camera_url = build_camera_url(cfg)
    storage = support_dir() / "storage"
    logs = support_dir() / "logs"
    yolo = install_dir() / "models" / "plate_yolov8.pt"

    lines = [
        f"SITE_ID={cfg.site_id}",
        f"CAMERA_ID={cfg.camera_id}",
        f"DIRECTION={cfg.direction}",
        f"CAMERA_RTSP_URL={camera_url}",
        "",
        f"BACKEND_URL={cfg.backend_url.rstrip('/')}",
        f"ANPR_AGENT_TOKEN={env_value(cfg.anpr_token)}",
        "",
        "BOOKING_HINTS_ENABLED=true",
        "BOOKING_HINTS_REFRESH_SECONDS=600",
        "",
        f"YOLO_MODEL_PATH={yolo}",
        "MIN_CONFIDENCE=0.55",
        "OCR_MIN_CONFIDENCE=0.55",
        "YOLO_CONFIDENCE=0.15",
        "YOLO_MAX_IMAGE_WIDTH=1280",
        "PLATE_COOLDOWN_SECONDS=60",
        "",
        "FRAME_INTERVAL_MS=1000",
        "MOTION_GATE_ENABLED=true",
        "MOTION_SCAN_INTERVAL_MS=5000",
        "MOTION_ACTIVE_SECONDS=45",
        "MOTION_THRESHOLD=0.012",
        "",
        f"STORAGE_DIR={storage}",
        "SAVE_SNAPSHOTS=false",
        "FRAME_RETENTION_HOURS=24",
        "FRAME_MAX_FILES=200",
        "FRAME_MAX_STORAGE_MB=256",
        "",
        "HEALTH_HOST=0.0.0.0",
        "HEALTH_PORT=8080",
        "AGENT_AUTO_START=true",
        "",
        f"LOG_DIR={logs}",
        "LOG_LEVEL=INFO",
    ]
    return "\n".join(lines) + "\n"


def _run(
    cmd: list[str],
    cwd: Path,
    log: Callable[[str], None],
    *,
    optional: bool = False,
    status_label: str | None = None,
    heartbeat_seconds: int = 20,
) -> None:
    if status_label:
        log(status_label)
    else:
        log(f"Kör: {' '.join(cmd)}")

    stop = threading.Event()
    started = time.time()

    def heartbeat() -> None:
        label = status_label or "Arbetar"
        while not stop.wait(heartbeat_seconds):
            elapsed = int(time.time() - started)
            mins, secs = divmod(elapsed, 60)
            log(f"{label} ({mins}:{secs:02d}) — stäng inte fönstret, detta är normalt")

    hb_thread: threading.Thread | None = None
    if status_label:
        hb_thread = threading.Thread(target=heartbeat, daemon=True)
        hb_thread.start()

    flags = 0
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags = subprocess.CREATE_NO_WINDOW
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            creationflags=flags,
        )
    finally:
        stop.set()

    if proc.returncode == 0:
        return
    detail = (proc.stderr or proc.stdout or "").strip()
    if optional:
        if detail:
            log(f"Varning: {detail[:500]}")
        return
    message = "Kommandot misslyckades"
    if detail:
        message = f"{message}: {detail[:800]}"
    raise RuntimeError(message)


def _pip_install(py: Path, requirements_file: str, label: str, app_dir: Path, log: Callable[[str], None]) -> None:
    _run(
        [
            str(py),
            "-m",
            "pip",
            "install",
            "-q",
            "--disable-pip-version-check",
            "-r",
            requirements_file,
        ],
        app_dir,
        log,
        status_label=label,
    )


def _venv_python(app_dir: Path) -> Path:
    if sys.platform == "win32":
        return app_dir / ".venv" / "Scripts" / "python.exe"
    return app_dir / ".venv" / "bin" / "python"


def _venv_is_usable(app_dir: Path) -> bool:
    py = _venv_python(app_dir)
    if not py.is_file():
        return False
    flags = 0
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags = subprocess.CREATE_NO_WINDOW
    try:
        proc = subprocess.run(
            [str(py), "-c", "import sys"],
            cwd=app_dir,
            capture_output=True,
            timeout=30,
            creationflags=flags,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _resolve_installer_python() -> str:
    if sys.platform == "win32":
        from installer.prerequisites import find_python_executable

        found = find_python_executable()
        if found:
            return found
    return sys.executable


def setup_python_env(app_dir: Path, log: Callable[[str], None]) -> Path:
    venv = app_dir / ".venv"
    python = _resolve_installer_python()

    if venv.exists() and not _venv_is_usable(app_dir):
        log("Rensar trasig Python-miljö...")
        shutil.rmtree(venv, ignore_errors=True)

    if not venv.exists():
        log("Skapar Python-miljö...")
        _run([python, "-m", "venv", str(venv)], app_dir, log)

    py = _venv_python(app_dir)
    if not py.is_file():
        raise RuntimeError(f"Python-miljön skapades inte korrekt: {py}")

    log("Installerar programkomponenter (första gången kan ta 10–15 minuter)…")
    _run(
        [str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", "--upgrade", "pip"],
        app_dir,
        log,
        optional=True,
    )
    _pip_install(
        py,
        "requirements.txt",
        "Steg 1/4: Grundpaket (kamera och nätverk)…",
        app_dir,
        log,
    )
    _pip_install(
        py,
        "requirements-ai.txt",
        "Steg 2/4: AI för skyltigenkänning (YOLO) — största nedladdningen, kan ta 5–15 min",
        app_dir,
        log,
    )
    _pip_install(
        py,
        "requirements-ocr.txt",
        "Steg 3/4: OCR för registreringsskyltar…",
        app_dir,
        log,
    )

    model = app_dir / "models" / "plate_yolov8.pt"
    if not model.exists():
        log("Steg 4/4: Laddar ner ANPR-modell…")
        if sys.platform == "win32":
            url = "https://huggingface.co/Koushim/yolov8-license-plate-detection/resolve/main/best.pt"
            model.parent.mkdir(parents=True, exist_ok=True)
            import urllib.request

            urllib.request.urlretrieve(url, model)
        else:
            script = app_dir / "scripts" / "download-yolo-model.sh"
            if script.exists():
                _run(["bash", str(script)], app_dir, log)

    return py


def copy_application(source: Path, target: Path, log: Callable[[str], None]) -> None:
    log(f"Kopierar till {target}...")
    target.mkdir(parents=True, exist_ok=True)
    exclude = {
        ".venv",
        ".git",
        "__pycache__",
        "storage",
        "logs",
        ".env",
        "models",
    }
    for item in source.iterdir():
        if item.name in exclude:
            continue
        dest = target / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(
                item,
                dest,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
            )
        else:
            shutil.copy2(item, dest)


def write_config(cfg: InstallConfig, log: Callable[[str], None]) -> Path:
    support = support_dir()
    support.mkdir(parents=True, exist_ok=True)
    (support / "storage" / "frames").mkdir(parents=True, exist_ok=True)
    (support / "storage" / "events").mkdir(parents=True, exist_ok=True)
    (support / "logs").mkdir(parents=True, exist_ok=True)

    env_path = support / ".env"
    env_text = render_env(cfg)
    env_path.write_text(env_text, encoding="utf-8")

    app_env = install_dir() / ".env"
    app_env.write_text(env_text, encoding="utf-8")
    log(f"Konfiguration sparad: {env_path}")
    return env_path


def install_autostart(app_dir: Path, log: Callable[[str], None]) -> None:
    if sys.platform == "darwin":
        _install_mac_launchagent(app_dir, log)
    elif sys.platform == "win32":
        _install_windows_startup(app_dir, log)
    else:
        log("Autostart: starta manuellt med scripts/start.sh")


def _install_mac_launchagent(app_dir: Path, log: Callable[[str], None]) -> None:
    support = support_dir()
    plist_src = app_dir / "deploy" / "com.anpr.edge-agent.plist"
    plist_dst = Path.home() / "Library" / "LaunchAgents" / "com.anpr.edge-agent.plist"
    label = "com.anpr.edge-agent"

    text = plist_src.read_text(encoding="utf-8")
    text = text.replace("__INSTALL_DIR__", str(app_dir))
    text = text.replace("__SUPPORT_DIR__", str(support))
    plist_dst.parent.mkdir(parents=True, exist_ok=True)
    plist_dst.write_text(text, encoding="utf-8")

    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{label}"], check=False)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist_dst)], check=True)
    subprocess.run(["launchctl", "enable", f"gui/{uid}/{label}"], check=True)
    log("Autostart aktiverad (startar vid inloggning)")


def _install_windows_startup(app_dir: Path, log: Callable[[str], None]) -> None:
    startup = (
        Path(os.environ["APPDATA"])
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )
    startup.mkdir(parents=True, exist_ok=True)
    bat = startup / "ANPR Edge Agent.bat"
    run_script = app_dir / "scripts" / "run-agent.cmd"
    bat.write_text(
        f'@echo off\r\nstart "" /min "{run_script}"\r\n',
        encoding="utf-8",
    )
    log("Autostart aktiverad (startar vid inloggning)")


def create_dashboard_shortcut(log: Callable[[str], None]) -> None:
    if sys.platform == "darwin":
        cmd = Path.home() / "Desktop" / "ANPR.command"
        cmd.write_text(
            "#!/bin/bash\nopen 'http://127.0.0.1:8080'\n",
            encoding="utf-8",
        )
        os.chmod(cmd, 0o755)
        log(f"Genväg skapad: {cmd}")
    elif sys.platform == "win32":
        desktop = Path.home() / "Desktop" / "ANPR.url"
        desktop.write_text(
            "[InternetShortcut]\nURL=http://127.0.0.1:8080/\n",
            encoding="utf-8",
        )
        log(f"Genväg skapad: {desktop}")


def _pids_listening_on_port(port: int) -> set[str]:
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        creationflags=flags,
    )
    pids: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr = parts[1]
        remote_addr = parts[2]
        pid = parts[-1]
        if f":{port}" not in local_addr:
            continue
        if not remote_addr.endswith(":0"):
            continue
        if pid.isdigit() and pid != "0":
            pids.add(pid)
    return pids


def _stop_windows_agent_processes(app_dir: Path) -> None:
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    marker = str(app_dir).replace("'", "''")
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
        f"Where-Object {{ $_.CommandLine -like '*{marker}*' -and $_.CommandLine -like '*src.main*' }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        check=False,
        creationflags=flags,
    )


def stop_agent(app_dir: Path, log: Callable[[str], None] | None = None, *, port: int = 8080) -> None:
    def _log(msg: str) -> None:
        if log:
            log(msg)

    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        _stop_windows_agent_processes(app_dir)
        pids = _pids_listening_on_port(port)
        for pid in pids:
            subprocess.run(
                ["taskkill", "/F", "/PID", pid],
                check=False,
                creationflags=flags,
            )
        if pids:
            _log("Stoppade tidigare ANPR-process…")
            time.sleep(1)
        return

    if sys.platform == "darwin":
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/com.anpr.edge-agent"],
            check=False,
        )
        time.sleep(1)


def start_agent(app_dir: Path, log: Callable[[str], None]) -> None:
    stop_agent(app_dir, log)
    if sys.platform == "darwin":
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/com.anpr.edge-agent"],
            check=False,
        )
        time.sleep(2)
    elif sys.platform == "win32":
        run = app_dir / "scripts" / "run-agent.cmd"
        subprocess.Popen(
            ["cmd", "/c", str(run)],
            cwd=app_dir,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        time.sleep(3)
    else:
        py = app_dir / ".venv" / "bin" / "python"
        subprocess.Popen([str(py), "-m", "src.main"], cwd=app_dir)


def read_version(app_dir: Path) -> str | None:
    init_file = app_dir / "src" / "__init__.py"
    if not init_file.exists():
        return None
    for line in init_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def is_installed() -> bool:
    return (support_dir() / ".env").is_file() and (install_dir() / "src" / "main.py").is_file()


def install_status_payload() -> dict:
    from installer.updater import remote_update_status

    installed = is_installed()
    target = install_dir()
    source = repo_root()
    current = read_version(target) if installed else None
    available = read_version(source)
    local_update = bool(installed and available and (not current or current != available))
    remote = remote_update_status(current) if installed else {}

    payload: dict = {
        "installed": installed,
        "currentVersion": current,
        "availableVersion": available,
        "updateAvailable": local_update or remote.get("remoteUpdateAvailable", False),
        "localUpdateAvailable": local_update,
        "installDir": str(target),
        **remote,
    }
    if installed:
        saved = read_installed_config()
        if saved:
            payload["savedConfig"] = saved
    return payload


def run_update(log: Callable[[str], None], *, open_browser: bool = True) -> None:
    if not is_installed():
        raise RuntimeError("ANPR är inte installerat — kör en full installation först.")

    target = install_dir()
    source = repo_root()

    log("Uppdaterar programfiler...")
    copy_application(source, target, log)
    log("Uppdaterar Python-paket...")
    setup_python_env(target, log)
    install_autostart(target, log)
    start_agent(target, log)
    log("Uppdatering klar — kamera och token är oförändrade.")
    if open_browser:
        webbrowser.open("http://127.0.0.1:8080")


def run_install(cfg: InstallConfig, log: Callable[[str], None], *, open_browser: bool = True) -> None:
    source = repo_root()
    target = install_dir()
    already = is_installed()

    if already:
        log("Uppdaterar konfiguration…")

    from installer.token_check import validate_backend_credentials

    log("Verifierar token mot backend…")
    ok, message = validate_backend_credentials(
        site_id=cfg.site_id,
        backend_url=cfg.backend_url,
        token=cfg.anpr_token,
    )
    if not ok:
        raise RuntimeError(message)
    log(message)

    copy_application(source, target, log)
    setup_python_env(target, log)
    write_config(cfg, log)
    install_autostart(target, log)
    create_dashboard_shortcut(log)
    start_agent(target, log)
    log("Klart!")
    if open_browser:
        webbrowser.open("http://127.0.0.1:8080")


def check_prerequisites() -> list[str]:
    from installer.prerequisites import check_prerequisites as _check

    return _check()
