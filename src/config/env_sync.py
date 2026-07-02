"""Sync installed config from support directory before loading settings."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def installed_support_env() -> Path | None:
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if not local:
            return None
        path = Path(local) / "anpr-edge-agent" / "data" / ".env"
    elif sys.platform == "darwin":
        path = Path.home() / "Library/Application Support/anpr-edge-agent/.env"
    else:
        return None
    return path if path.is_file() else None


def installed_app_dir() -> Path | None:
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if not local:
            return None
        return Path(local) / "anpr-edge-agent"
    if sys.platform == "darwin":
        return Path.home() / "Applications" / "anpr-edge-agent"
    return None


def project_env_file() -> Path | None:
    local = Path(".env")
    if local.is_file():
        return local.resolve()
    return None


def running_from_installed_app() -> bool:
    install = installed_app_dir()
    if install is None:
        return False
    try:
        return Path.cwd().resolve() == install.resolve()
    except OSError:
        return False


def sync_installed_env(target_dir: Path | None = None) -> Path | None:
    """Return installed support .env path without copying over local edits."""
    return installed_support_env()
