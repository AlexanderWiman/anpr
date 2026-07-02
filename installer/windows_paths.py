"""Windows shell folder paths (works with localized Desktop e.g. Skrivbord)."""

from __future__ import annotations

import sys
from pathlib import Path

# CSIDL_DESKTOPDIRECTORY — folder where Desktop items are stored
_CSIDL_DESKTOPDIRECTORY = 0x0010


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
