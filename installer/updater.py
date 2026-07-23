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
_RELEASE_TAG = re.compile(r"^v?\d{4}\.\d{2}\.\d{2}\.\d+$")


def looks_like_release_tag(value: str | None) -> bool:
    if not value:
        return False
    return bool(_RELEASE_TAG.match(value.strip()))


def parse_version(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    parts: list[int] = []
    for piece in re.split(r"[^0-9]+", value):
        if piece.isdigit():
            parts.append(int(piece))
    return tuple(parts)


def is_newer(remote: str | None, current: str | None) -> bool:
    if looks_like_release_tag(remote):
        return False
    remote_t = parse_version(remote)
    current_t = parse_version(current)
    if not remote_t:
        return False
    if not current_t:
        return True
    return remote_t > current_t


def display_version(value: str | None, *, fallback: str | None = None) -> str | None:
    """Prefer semver for UI; release tags (2026.07.23.5) are not user-facing versions."""
    if value and not looks_like_release_tag(value):
        return value
    return fallback


def update_repo() -> str:
    return os.environ.get("ANPR_UPDATE_REPO", DEFAULT_REPO).strip()


def update_ref() -> str:
    return os.environ.get("ANPR_UPDATE_REF", DEFAULT_REF).strip()


def _http_get(url: str, *, accept: str = "application/json") -> bytes:
    import ssl

    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
    )
    try:
        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    with urllib.request.urlopen(request, context=context, timeout=30) as response:
        return response.read()


def read_version_from_init_text(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def fetch_remote_version(repo: str | None = None, ref: str | None = None) -> str | None:
    repo = repo or update_repo()
    ref = ref or update_ref()
    candidates = [
        f"https://raw.githubusercontent.com/{repo}/{ref}/src/__init__.py",
        f"https://raw.githubusercontent.com/{repo}/{ref}/{AGENT_SUBDIR}/src/__init__.py",
    ]
    for url in candidates:
        try:
            data = _http_get(url, accept="text/plain").decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
        version = read_version_from_init_text(data)
        if version:
            return version
    return None


def _release_asset_download_url(payload: dict) -> str | None:
    for asset in payload.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name", ""))
        download = asset.get("browser_download_url")
        if name.endswith(".zip") and isinstance(download, str) and download:
            return download
    return None


def fetch_release_tag(repo: str | None = None) -> tuple[str | None, str | None]:
    """Return (release tag, download_url) from latest GitHub Release if any."""
    repo = repo or update_repo()
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        payload = json.loads(_http_get(url).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None, None
    tag = str(payload.get("tag_name", "")).lstrip("v") or None
    download = _release_asset_download_url(payload)
    if download:
        return tag, download
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
    repo = update_repo()
    ref = update_ref()
    release_tag, release_download = fetch_release_tag(repo)
    release_semver = (
        fetch_remote_version(repo, f"v{release_tag}") if release_tag else None
    )
    main_version = fetch_remote_version(repo, ref)
    github_version = release_semver or main_version
    github_download = release_download or f"https://github.com/{repo}/archive/refs/heads/{ref}.zip"

    backend_version: str | None = None
    backend_download: str | None = None
    backend_url = _read_installed_backend_url()
    if backend_url:
        backend_info = fetch_backend_agent_version(backend_url)
        if backend_info:
            backend_version = backend_info["version"]
            backend_download = backend_info.get("downloadUrl")

    # IT-approved release via backend when it advertises a newer version.
    if backend_version and is_newer(backend_version, current_version):
        return {
            "remoteVersion": backend_version,
            "remoteUpdateAvailable": True,
            "updateSource": "backend",
            "downloadUrl": backend_download or github_download,
            "updateRepo": repo,
        }

    # Installed build is at or ahead of backend-approved version — do not fall back to
    # GitHub release tags (e.g. 2026.07.23.4) which are not comparable to semver.
    if backend_version and not is_newer(backend_version, current_version):
        return {
            "remoteVersion": backend_version,
            "remoteUpdateAvailable": False,
            "updateSource": "backend",
            "downloadUrl": backend_download,
            "updateRepo": repo,
            "backendVersion": backend_version,
            "githubVersion": github_version,
        }

    # Fallback to GitHub when backend is missing, stale, or not ahead of installed build.
    if github_version and is_newer(github_version, current_version):
        return {
            "remoteVersion": github_version,
            "remoteUpdateAvailable": True,
            "updateSource": "release" if release_tag else "main",
            "downloadUrl": github_download,
            "updateRepo": repo,
        }

    remote_version = backend_version or github_version
    if backend_version and github_version:
        best = github_version if is_newer(github_version, backend_version) else backend_version
    else:
        best = remote_version
    return {
        "remoteVersion": best,
        "remoteUpdateAvailable": False,
        "updateSource": "backend" if backend_version else ("release" if release_tag else "main"),
        "updateRepo": repo,
        "backendVersion": backend_version,
        "githubVersion": github_version,
    }


def _download_accept(url: str) -> str:
    if "api.github.com" in url and "/zipball/" in url:
        return "application/vnd.github+json"
    return "application/octet-stream"


def _find_agent_dir(extract_root: Path) -> Path:
    search_roots = [extract_root, *extract_root.iterdir()]
    for base in search_roots:
        if not base.is_dir():
            continue
        if (base / "src" / "main.py").is_file():
            return base
        nested = base / AGENT_SUBDIR
        if (nested / "src" / "main.py").is_file():
            return nested
    raise FileNotFoundError("Kunde inte hitta ANPR-agent i nedladdningen")


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
    archive = _http_get(url, accept=_download_accept(url))
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
        create_dashboard_shortcut,
    )

    if not is_installed():
        raise RuntimeError("ANPR är inte installerat — kör en full installation först.")

    current = read_version(install_dir())
    status = remote_update_status(current)
    download_url = status.get("downloadUrl")

    staging = download_release_source(log, download_url=download_url)
    target = install_dir()
    try:
        log("Installerar nedladdad version…")
        copy_application(staging, target, log)
        log("Uppdaterar Python-paket…")
        setup_python_env(target, log)
        install_autostart(target, log)
        create_dashboard_shortcut(log)
        start_agent(target, log)
        remote = status.get("remoteVersion") or "ny"
        log(f"Uppdatering klar (version {remote}). Kamera och token är oförändrade.")
    finally:
        shutil.rmtree(staging, ignore_errors=True)
