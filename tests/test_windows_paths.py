"""Tests for Windows install path selection."""

from pathlib import Path

from installer import windows_paths as wp


def test_torch_path_limit_detects_long_localappdata(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\Olles Falun\AppData\Local")
    local = wp.localappdata_install_dir()
    assert wp.install_path_too_long_for_torch(local) is True


def test_torch_path_limit_allows_short_localappdata(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\alex\AppData\Local")
    local = wp.localappdata_install_dir()
    assert wp.install_path_too_long_for_torch(local) is False


def test_recommended_install_dir_uses_programdata_on_windows(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\alex\AppData\Local")
    monkeypatch.setenv("ProgramData", r"C:\ProgramData")
    assert wp.recommended_windows_install_dir().as_posix().replace("/", "\\") == (
        r"C:\ProgramData\anpr-edge-agent"
    )


def test_resolve_install_dir_prefers_existing_localappdata(monkeypatch, tmp_path):
    local = tmp_path / "local" / "anpr-edge-agent"
    programdata = tmp_path / "programdata" / "anpr-edge-agent"
    local.mkdir(parents=True)
    (local / "src").mkdir()
    (local / "src" / "main.py").write_text("", encoding="utf-8")

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("ProgramData", str(tmp_path / "programdata"))

    assert wp.resolve_windows_install_dir() == local
    assert wp.resolve_windows_support_dir(local) == local / "data"
