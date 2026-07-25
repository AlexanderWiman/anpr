from src.services.dashboard_settings import build_dashboard_settings_payload


def test_build_dashboard_settings_payload_masks_secrets(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "SITE_ID=stockholm",
                "ANPR_AGENT_TOKEN=super-secret-token",
                "CAMERA_RTSP_URL=rtsp://user:pass@192.168.1.10:554/stream1",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.services.dashboard_settings.settings_env_path",
        lambda: str(env_path),
    )

    payload = build_dashboard_settings_payload()

    assert payload["configPath"] == str(env_path)
    assert payload["settings"]["SITE_ID"] == "stockholm"
    assert payload["settings"]["ANPR_AGENT_TOKEN"] == "su…en"
    assert payload["settings"]["CAMERA_RTSP_URL"] == "rtsp://***@192.168.1.10:554/stream1"
