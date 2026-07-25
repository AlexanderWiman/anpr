import json
from unittest.mock import patch

from src.services.local_update import (
    build_update_status_payload,
    local_update_state_path,
    read_local_update_state,
)


def test_read_local_update_state_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.services.local_update.support_dir",
        lambda: tmp_path,
        raising=False,
    )
    monkeypatch.setattr(
        "installer.engine.support_dir",
        lambda: tmp_path,
    )
    assert read_local_update_state() is None


def test_build_update_status_payload_marks_running_job(tmp_path, monkeypatch):
    monkeypatch.setattr("installer.engine.support_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "src.services.local_update.local_update_state_path",
        lambda: tmp_path / "local-update.json",
    )
    (tmp_path / "local-update.json").write_text(
        json.dumps({"status": "running", "message": "Laddar ner…"}),
        encoding="utf-8",
    )

    with patch("installer.engine.is_installed", return_value=True), patch(
        "installer.engine.install_dir", return_value=tmp_path
    ), patch("installer.engine.read_version", return_value="1.0.49"), patch(
        "installer.updater.remote_update_status",
        return_value={
            "remoteVersion": "1.0.50",
            "remoteUpdateAvailable": True,
            "updateSource": "backend",
        },
    ), patch("installer.updater.display_version", return_value="1.0.50"):
        payload = build_update_status_payload()

    assert payload["currentVersion"] == "1.0.49"
    assert payload["updateAvailable"] is False
    assert payload["job"]["status"] == "running"


def test_build_update_status_payload_clears_stale_failed_job(tmp_path, monkeypatch):
    monkeypatch.setattr("installer.engine.support_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "src.services.local_update.local_update_state_path",
        lambda: tmp_path / "local-update.json",
    )
    state_path = tmp_path / "local-update.json"
    state_path.write_text(
        json.dumps(
            {
                "status": "failed",
                "error": "name 'stop_agent' is not defined",
                "message": "Uppdatering misslyckades",
            }
        ),
        encoding="utf-8",
    )

    with patch("installer.engine.is_installed", return_value=True), patch(
        "installer.engine.install_dir", return_value=tmp_path
    ), patch("installer.engine.read_version", return_value="1.0.53"), patch(
        "installer.updater.remote_update_status",
        return_value={
            "remoteVersion": "1.0.53",
            "remoteUpdateAvailable": False,
            "updateSource": "backend",
        },
    ), patch("installer.updater.display_version", return_value="1.0.53"):
        payload = build_update_status_payload()

    assert payload["updateAvailable"] is False
    assert payload["job"] is None
    assert not state_path.is_file()
