from installer.updater import (
    _download_accept,
    _release_asset_download_url,
    display_version,
    is_newer,
    looks_like_release_tag,
    parse_version,
    remote_update_status,
)


def test_parse_version():
    assert parse_version("1.0.17") == (1, 0, 17)
    assert parse_version("v1.0.16") == (1, 0, 16)
    assert parse_version("2026.07.23.4") == (2026, 7, 23, 4)


def test_is_newer():
    assert is_newer("1.0.17", "1.0.16")
    assert not is_newer("1.0.16", "1.0.17")
    assert not is_newer("1.0.17", "1.0.17")
    assert not is_newer("2026.07.23.5", "1.0.41")
    assert looks_like_release_tag("2026.07.23.5")
    assert not looks_like_release_tag("1.0.41")
    assert display_version("2026.07.23.5", fallback="1.0.41") == "1.0.41"


def test_local_update_only_when_installer_is_newer():
    current = "1.0.17"
    older_installer = "1.0.16"
    newer_installer = "1.0.18"
    assert not is_newer(older_installer, current)
    assert is_newer(newer_installer, current)


def test_release_asset_download_url_prefers_zip_asset():
    payload = {
        "assets": [
            {
                "name": "anpr-edge-agent-20260723.4.zip",
                "browser_download_url": "https://github.com/example/releases/download/v1/foo.zip",
            }
        ]
    }
    assert (
        _release_asset_download_url(payload)
        == "https://github.com/example/releases/download/v1/foo.zip"
    )


def test_download_accept_for_zipball():
    assert (
        _download_accept("https://api.github.com/repos/o/r/zipball/v1")
        == "application/vnd.github+json"
    )
    assert (
        _download_accept("https://github.com/o/r/releases/download/v1/agent.zip")
        == "application/octet-stream"
    )


def test_remote_update_status_respects_backend_when_current(monkeypatch):
    monkeypatch.setattr(
        "installer.updater.fetch_release_tag",
        lambda repo=None: ("2026.07.23.4", "https://api.github.com/repos/o/r/zipball/v1"),
    )
    monkeypatch.setattr(
        "installer.updater.fetch_remote_version",
        lambda repo=None, ref=None: "1.0.40" if ref and ref.startswith("v2026") else "1.0.40",
    )
    monkeypatch.setattr(
        "installer.updater._read_installed_backend_url",
        lambda: "https://backend.example",
    )
    monkeypatch.setattr(
        "installer.updater.fetch_backend_agent_version",
        lambda url: {
            "version": "1.0.40",
            "downloadUrl": "https://github.com/example/releases/download/v1/agent.zip",
        },
    )

    status = remote_update_status("1.0.40")
    assert status["remoteUpdateAvailable"] is False
    assert status["remoteVersion"] == "1.0.40"
    assert status["updateSource"] == "backend"


def test_remote_update_status_uses_release_semver_not_tag(monkeypatch):
    monkeypatch.setattr(
        "installer.updater.fetch_release_tag",
        lambda repo=None: (
            "2026.07.23.4",
            "https://github.com/example/releases/download/v1/agent.zip",
        ),
    )
    monkeypatch.setattr(
        "installer.updater.fetch_remote_version",
        lambda repo=None, ref=None: "1.0.40" if ref and ref.startswith("v2026") else None,
    )
    monkeypatch.setattr("installer.updater._read_installed_backend_url", lambda: None)

    status = remote_update_status("1.0.40")
    assert status["remoteUpdateAvailable"] is False
    assert status["githubVersion"] == "1.0.40"
