"""Sync installed config from support directory before loading settings."""

from __future__ import annotations

import os
import shutil
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


def sync_installed_env(target_dir: Path | None = None) -> Path | None:
    """Copy support .env into the app directory so Settings() loads the installed config."""
    source = installed_support_env()
    if source is None:
        return None

    root = target_dir or Path.cwd()
    dest = root / ".env"
    if dest.resolve() == source.resolve():
        return dest

    shutil.copy2(source, dest)
    return dest
