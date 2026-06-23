"""Cross-platform install engine for ANPR edge agent."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


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


def render_env(cfg: InstallConfig) -> str:
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
        f"ANPR_AGENT_TOKEN={cfg.anpr_token}",
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


def _run(cmd: list[str], cwd: Path, log: Callable[[str], None]) -> None:
    log(f"Kör: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


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


def setup_python_env(app_dir: Path, log: Callable[[str], None]) -> Path:
    venv = app_dir / ".venv"
    python = sys.executable

    if not venv.exists():
        log("Skapar Python-miljö...")
        _run([python, "-m", "venv", str(venv)], app_dir, log)

    if sys.platform == "win32":
        pip = venv / "Scripts" / "pip.exe"
        py = venv / "Scripts" / "python.exe"
    else:
        pip = venv / "bin" / "pip"
        py = venv / "bin" / "python"

    log("Installerar paket (kan ta några minuter)...")
    _run([str(pip), "install", "-q", "--upgrade", "pip"], app_dir, log)
    _run(
        [str(pip), "install", "-q", "-r", "requirements.txt", "-r", "requirements-ai.txt", "-r", "requirements-ocr.txt"],
        app_dir,
        log,
    )

    model = app_dir / "models" / "plate_yolov8.pt"
    if not model.exists():
        log("Laddar ner ANPR-modell...")
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


def start_agent(app_dir: Path, log: Callable[[str], None]) -> None:
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

    return {
        "installed": installed,
        "currentVersion": current,
        "availableVersion": available,
        "updateAvailable": local_update or remote.get("remoteUpdateAvailable", False),
        "localUpdateAvailable": local_update,
        "installDir": str(target),
        **remote,
    }


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
