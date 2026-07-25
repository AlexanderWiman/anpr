from unittest.mock import patch

from installer.manual_update_cli import main


def test_manual_update_cli_uses_backend_info(monkeypatch):
    calls: list[dict] = []

    monkeypatch.setattr(
        "installer.manual_update_cli._read_installed_backend_url",
        lambda: "https://backend.example",
    )
    monkeypatch.setattr(
        "installer.manual_update_cli.fetch_backend_agent_version",
        lambda _url: {
            "version": "1.0.54",
            "downloadUrl": "https://example.com/agent.zip",
        },
    )

    def _fake_job(request_id, *, download_url, target_version):
        calls.append(
            {
                "request_id": request_id,
                "download_url": download_url,
                "target_version": target_version,
            }
        )

    monkeypatch.setattr("installer.manual_update_cli.run_remote_update_job", _fake_job)

    assert main([]) == 0
    assert len(calls) == 1
    assert calls[0]["download_url"] == "https://example.com/agent.zip"
    assert calls[0]["target_version"] == "1.0.54"
