"""Windows-safe subprocess helpers (avoid cp1252 decode errors on pip output)."""

from __future__ import annotations

import subprocess
import sys


def subprocess_flags() -> int:
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return subprocess.CREATE_NO_WINDOW
    return 0


def subprocess_text_kwargs() -> dict:
    if sys.platform == "win32":
        return {"encoding": "utf-8", "errors": "replace"}
    return {}


def run_checked(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run with safe text decoding on Windows."""
    run_kwargs = {
        "check": True,
        "creationflags": subprocess_flags(),
        **subprocess_text_kwargs(),
    }
    run_kwargs.update(kwargs)
    return subprocess.run(cmd, **run_kwargs)
