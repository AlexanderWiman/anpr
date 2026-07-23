"""Windows shell folder paths (works with localized Desktop e.g. Skrivbord)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# CSIDL_DESKTOPDIRECTORY — folder where Desktop items are stored
_CSIDL_DESKTOPDIRECTORY = 0x0010

# PyTorch DLL loading fails on Windows when the venv path is too long (WinError 206).
_TORCH_LIB_SUFFIX = Path(".venv") / "Lib" / "site-packages" / "torch" / "lib"
_TORCH_PATH_LIMIT = 85
_INSTALL_MARKER = Path("src") / "main.py"


def _windows_path_length(path: Path) -> int:
    return len(str(path).replace("/", "\\"))


def localappdata_install_dir() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "anpr-edge-agent"


def programdata_install_dir() -> Path:
    return Path(os.environ["ProgramData"]) / "anpr-edge-agent"


def torch_lib_path(install_root: Path) -> Path:
    return install_root / _TORCH_LIB_SUFFIX


def install_path_too_long_for_torch(install_root: Path) -> bool:
    torch_len = _windows_path_length(torch_lib_path(install_root))
    if torch_len >= _TORCH_PATH_LIMIT:
        return True
    if install_root == localappdata_install_dir():
        localappdata = os.environ.get("LOCALAPPDATA", "")
        if " " in localappdata and torch_len >= 80:
            return True
    return False


def recommended_windows_install_dir() -> Path:
    # Workshop PCs: always install under ProgramData (shorter path, works with PyTorch).
    return programdata_install_dir()


def resolve_windows_install_dir() -> Path:
    programdata = programdata_install_dir()
    local = localappdata_install_dir()
    if (programdata / _INSTALL_MARKER).is_file():
        return programdata
    if (local / _INSTALL_MARKER).is_file():
        return local
    return recommended_windows_install_dir()


def resolve_windows_support_dir(install_root: Path) -> Path:
    programdata_support = programdata_install_dir() / "data"
    local_support = localappdata_install_dir() / "data"
    if (programdata_support / ".env").is_file():
        return programdata_support
    if (local_support / ".env").is_file():
        return local_support
    return install_root / "data"


def windows_desktop_dir() -> Path:
    if sys.platform != "win32":
        return Path.home() / "Desktop"

    import ctypes
    from ctypes import wintypes

    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, _CSIDL_DESKTOPDIRECTORY, None, 0, buf)
    if result != 0:
        return Path.home() / "Desktop"
    return Path(buf.value)
