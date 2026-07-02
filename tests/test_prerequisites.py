"""Tests for prerequisite detection."""

import os
import sys
from unittest.mock import patch

from installer import prerequisites as prereq


def test_windows_store_stub_detection():
    assert prereq._is_windows_store_stub(
        r"C:\Users\me\AppData\Local\Microsoft\WindowsApps\python.exe"
    )
    assert not prereq._is_windows_store_stub(
        r"C:\Users\me\AppData\Local\Programs\Python\Python312\python.exe"
    )


def test_find_python_executable_uses_current_interpreter_on_unix():
    if sys.platform == "win32":
        return
    found = prereq.find_python_executable()
    assert found
    assert prereq._python_version_ok(found)


def test_get_prerequisite_status_reports_python_on_unix():
    if sys.platform == "win32":
        return
    items = {item.id: item for item in prereq.get_prerequisite_status()}
    assert items["python"].ok


def test_find_ffmpeg_in_winget_packages_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(prereq, "refresh_windows_path", lambda: None)
    local = tmp_path / "AppData" / "Local"
    pkg_bin = (
        local
        / "Microsoft"
        / "WinGet"
        / "Packages"
        / "Gyan.FFmpeg_abc"
        / "ffmpeg-8.1-full_build"
        / "bin"
    )
    pkg_bin.mkdir(parents=True)
    (pkg_bin / "ffmpeg.exe").write_bytes(b"")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("PATH", "")
    assert prereq.find_ffmpeg() is not None


def test_refresh_windows_path_merges_registry(monkeypatch, tmp_path):
    import types

    monkeypatch.setattr(sys, "platform", "win32")
    ffmpeg_dir = tmp_path / "ffmpeg-bin"
    ffmpeg_dir.mkdir()
    (ffmpeg_dir / "ffmpeg.exe").write_bytes(b"")

    class FakeKey:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def QueryValueEx(self, _name):
            return (str(ffmpeg_dir), 1)

    fake_winreg = types.ModuleType("winreg")
    fake_winreg.HKEY_CURRENT_USER = 1
    fake_winreg.HKEY_LOCAL_MACHINE = 2
    fake_winreg.OpenKey = lambda *_args, **_kwargs: FakeKey()

    monkeypatch.setenv("PATH", "")
    with patch.dict(sys.modules, {"winreg": fake_winreg}):
        prereq.refresh_windows_path()

    assert str(ffmpeg_dir) in os.environ["PATH"]


def test_run_optional_does_not_raise(tmp_path):
    from installer.engine import _run

    log_messages: list[str] = []

    def log(msg: str) -> None:
        log_messages.append(msg)

    _run(["false"], tmp_path, log, optional=True)
    assert log_messages
