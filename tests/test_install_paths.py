"""Tests for installed path resolution."""

from pathlib import Path

from src.config import install_paths as paths


def test_resolve_support_env_prefers_programdata(monkeypatch, tmp_path):
    programdata = tmp_path / "programdata" / "anpr-edge-agent"
    local = tmp_path / "local" / "anpr-edge-agent"
    programdata.mkdir(parents=True)
    local.mkdir(parents=True)
    (programdata / "data").mkdir()
    (programdata / "data" / ".env").write_text("SITE_ID=falun\n", encoding="utf-8")

    monkeypatch.setenv("ProgramData", str(tmp_path / "programdata"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(paths.sys, "platform", "win32")

    assert paths.resolve_installed_support_env() == programdata / "data" / ".env"


def test_resolve_app_dir_from_programdata(monkeypatch, tmp_path):
    root = tmp_path / "programdata" / "anpr-edge-agent"
    (root / "src").mkdir(parents=True)
    (root / "src" / "main.py").write_text("", encoding="utf-8")

    monkeypatch.setenv("ProgramData", str(tmp_path / "programdata"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.chdir(tmp_path)

    assert paths.resolve_installed_app_dir() == root
