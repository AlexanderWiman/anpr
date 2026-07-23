"""Resolve installed ANPR paths on Windows (ProgramData + legacy LOCALAPPDATA)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_INSTALL_MARKER = Path("src") / "main.py"
_ENV_RELATIVE = Path("data") / ".env"


def _windows_install_roots() -> list[Path]:
    roots: list[Path] = []
    programdata = os.environ.get("ProgramData", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if programdata:
        roots.append(Path(programdata) / "anpr-edge-agent")
    if localappdata:
        legacy = Path(localappdata) / "anpr-edge-agent"
        if legacy not in roots:
            roots.append(legacy)
    return roots


def resolve_installed_app_dir() -> Path | None:
    if sys.platform == "win32":
        try:
            cwd = Path.cwd().resolve()
            if (cwd / _INSTALL_MARKER).is_file():
                return cwd
        except OSError:
            pass
        for root in _windows_install_roots():
            if (root / _INSTALL_MARKER).is_file():
                return root
        return None
    if sys.platform == "darwin":
        root = Path.home() / "Applications" / "anpr-edge-agent"
        return root if (root / _INSTALL_MARKER).is_file() else None
    return None


def resolve_installed_support_env() -> Path | None:
    if sys.platform == "win32":
        for root in _windows_install_roots():
            env_path = root / _ENV_RELATIVE
            if env_path.is_file():
                return env_path
        return None
    if sys.platform == "darwin":
        env_path = Path.home() / "Library/Application Support/anpr-edge-agent/.env"
        return env_path if env_path.is_file() else None
    return None
