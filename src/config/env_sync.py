"""Sync installed config from support directory before loading settings."""

from __future__ import annotations

import sys
from pathlib import Path

from src.config.install_paths import resolve_installed_app_dir, resolve_installed_support_env


def installed_support_env() -> Path | None:
    return resolve_installed_support_env()


def installed_app_dir() -> Path | None:
    return resolve_installed_app_dir()


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
