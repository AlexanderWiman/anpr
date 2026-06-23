from installer.updater import is_newer, parse_version


def test_parse_version():
    assert parse_version("1.0.17") == (1, 0, 17)
    assert parse_version("v1.0.16") == (1, 0, 16)


def test_is_newer():
    assert is_newer("1.0.17", "1.0.16")
    assert not is_newer("1.0.16", "1.0.17")
    assert not is_newer("1.0.17", "1.0.17")


def test_local_update_only_when_installer_is_newer():
    current = "1.0.17"
    older_installer = "1.0.16"
    newer_installer = "1.0.18"
    assert not is_newer(older_installer, current)
    assert is_newer(newer_installer, current)
