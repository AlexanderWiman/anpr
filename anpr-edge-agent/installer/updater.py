"""Check GitHub for updates and download new agent versions."""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

DEFAULT_REPO = "AlexanderWiman/anpr"
AGENT_SUBDIR = "anpr-edge-agent"
DEFAULT_REF = "main"
USER_AGENT = "anpr-edge-agent-updater/1.0"


def update_repo() -> str:
    return os.environ.get("ANPR_UPDATE_REPO", DEFAULT_REPO).strip()


def update_ref() -> str:
    return os.environ.get("ANPR_UPDATE_REF", DEFAULT_REF).strip()


def parse_version(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    parts: list[int] = []
    for piece in re.split(r"[^0-9]+", value):
        if piece.isdigit():
            parts.append(int(piece))
    return tuple(parts)


def is_newer(remote: str | None, current: str | None) -> bool:
    remote_t = parse_version(remote)
    current_t = parse_version(current)
    if not remote_t:
        return False
    if not current_t:
        return True
    return remote_t > current_t


def _http_get(url: str, *, accept: str = "application/json") -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def read_version_from_init_text(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def fetch_remote_version(repo: str | None = None, ref: str | None = None) -> str | None:
    repo = repo or update_repo()
    ref = ref or update_ref()
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{AGENT_SUBDIR}/src/__init__.py"
    try:
        data = _http_get(url, accept="text/plain").decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    return read_version_from_init_text(data)


def fetch_release_tag(repo: str | None = None) -> tuple[str | None, str | None]:
    """Return (version, zipball_url) from latest GitHub Release if any."""
    repo = repo or update_repo()
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        payload = json.loads(_http_get(url).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None, None
    tag = str(payload.get("tag_name", "")).lstrip("v") or None
    zip_url = payload.get("zipball_url")
    if isinstance(zip_url, str):
        return tag, zip_url
    return tag, None


def _read_installed_backend_url() -> str | None:
    from installer.engine import support_dir

    env_path = support_dir() / ".env"
    if not env_path.is_file():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("BACKEND_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def fetch_backend_agent_version(backend_url: str) -> dict | None:
    url = f"{backend_url.rstrip('/')}/api/anpr/agent-version"
    try:
        payload = json.loads(_http_get(url).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        return None
    download = payload.get("downloadUrl")
    return {
        "version": version.strip(),
        "downloadUrl": download if isinstance(download, str) and download else None,
    }


def remote_update_status(current_version: str | None) -> dict:
    backend_url = _read_installed_backend_url()
    if backend_url:
        backend_info = fetch_backend_agent_version(backend_url)
        if backend_info:
            remote_version = backend_info["version"]
            return {
                "remoteVersion": remote_version,
                "remoteUpdateAvailable": is_newer(remote_version, current_version),
                "updateSource": "backend",
                "updateRepo": update_repo(),
            }

    repo = update_repo()
    release_version, release_zip = fetch_release_tag(repo)
    main_version = fetch_remote_version(repo, update_ref())

    remote_version = release_version or main_version
    download_url = release_zip
    if not download_url:
        ref = update_ref()
        download_url = f"https://github.com/{repo}/archive/refs/heads/{ref}.zip"

    available = is_newer(remote_version, current_version)
    return {
        "remoteVersion": remote_version,
        "remoteUpdateAvailable": available,
        "updateSource": "release" if release_version else "main",
        "updateRepo": repo,
    }


def _find_agent_dir(extract_root: Path) -> Path:
    direct = extract_root / AGENT_SUBDIR
    if (direct / "src" / "main.py").is_file():
        return direct
    for child in extract_root.iterdir():
        if not child.is_dir():
            continue
        candidate = child / AGENT_SUBDIR
        if (candidate / "src" / "main.py").is_file():
            return candidate
        if (child / "src" / "main.py").is_file() and child.name == AGENT_SUBDIR:
            return child
    raise FileNotFoundError("Kunde inte hitta anpr-edge-agent i nedladdningen")


def download_release_source(
    log: Callable[[str], None],
    *,
    download_url: str | None = None,
) -> Path:
    repo = update_repo()
    url = download_url
    if not url:
        _tag, release_zip = fetch_release_tag(repo)
        if release_zip:
            url = release_zip
        else:
            url = f"https://github.com/{repo}/archive/refs/heads/{update_ref()}.zip"

    log("Laddar ner senaste versionen…")
    archive = _http_get(url, accept="application/octet-stream")
    temp_dir = Path(tempfile.mkdtemp(prefix="anpr-update-"))
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            zf.extractall(temp_dir)
        source = _find_agent_dir(temp_dir)
        staging = Path(tempfile.mkdtemp(prefix="anpr-update-src-"))
        shutil.copytree(source, staging, dirs_exist_ok=True)
        return staging
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_remote_update(log: Callable[[str], None]) -> None:
    from installer.engine import (
        install_autostart,
        install_dir,
        is_installed,
        read_version,
        setup_python_env,
        start_agent,
        copy_application,
    )

    if not is_installed():
        raise RuntimeError("ANPR är inte installerat — kör en full installation först.")

    current = read_version(install_dir())
    status = remote_update_status(current)
    download_url = None
    backend_url = _read_installed_backend_url()
    if backend_url:
        backend_info = fetch_backend_agent_version(backend_url)
        if backend_info:
            download_url = backend_info.get("downloadUrl")

    staging = download_release_source(log, download_url=download_url)
    target = install_dir()
    try:
        log("Installerar nedladdad version…")
        copy_application(staging, target, log)
        log("Uppdaterar Python-paket…")
        setup_python_env(target, log)
        install_autostart(target, log)
        start_agent(target, log)
        remote = status.get("remoteVersion") or "ny"
        log(f"Uppdatering klar (version {remote}). Kamera och token är oförändrade.")
    finally:
        shutil.rmtree(staging, ignore_errors=True)
