"""Isolated Python environment for the install wizard (avoids PEP 668 system pip)."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

_INSTALLER_DEPS = (
    "fastapi",
    "uvicorn",
    "httpx",
    "pydantic",
    "pydantic-settings",
    "python-dotenv",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def installer_venv_dir() -> Path:
    return repo_root() / ".installer-venv"


def venv_python() -> Path:
    if sys.platform == "win32":
        return installer_venv_dir() / "Scripts" / "python.exe"
    return installer_venv_dir() / "bin" / "python"


def running_in_installer_venv() -> bool:
    try:
        return Path(sys.executable).resolve() == venv_python().resolve()
    except OSError:
        return False


def _pip_install(python: Path, *packages: str) -> None:
    subprocess.run(
        [str(python), "-m", "pip", "install", "-q", "--disable-pip-version-check", *packages],
        check=True,
    )


def ensure_installer_venv(log: Callable[[str], None]) -> None:
    """Re-exec into .installer-venv when not already running there."""
    if running_in_installer_venv():
        try:
            import uvicorn  # noqa: F401
        except ImportError:
            log("Installerar Python-komponenter (första gången kan ta några minuter)...")
            _pip_install(Path(sys.executable), "--upgrade", "pip", *_INSTALLER_DEPS)
        return

    venv_dir = installer_venv_dir()
    py = venv_python()

    if not py.is_file():
        log("Skapar installationsmiljö (venv)...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        _pip_install(py, "--upgrade", "pip", *_INSTALLER_DEPS)
    else:
        try:
            subprocess.run(
                [str(py), "-c", "import uvicorn"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            log("Uppdaterar installationsmiljö...")
            _pip_install(py, "--upgrade", "pip", *_INSTALLER_DEPS)

    os.execv(str(py), [str(py), "-m", "installer", *sys.argv[1:]])
