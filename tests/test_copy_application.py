from pathlib import Path

from installer.engine import COPY_APPLICATION_EXCLUDE, copy_application


def test_copy_application_skips_dev_folders(tmp_path: Path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()

    (source / "src").mkdir()
    (source / "src" / "main.py").write_text("ok", encoding="utf-8")
    (source / ".github").mkdir()
    (source / ".github" / "workflows").mkdir(parents=True)
    (source / ".github" / "workflows" / "release.yml").write_text("ci", encoding="utf-8")
    (source / "tests").mkdir()
    (source / "tests" / "test_x.py").write_text("x", encoding="utf-8")

    target_github = target / ".github"
    target_github.mkdir(parents=True)
    (target_github / "workflows").mkdir()
    (target_github / "workflows" / "release.yml").write_text("old", encoding="utf-8")

    copy_application(source, target, log=lambda _msg: None)

    assert (target / "src" / "main.py").read_text(encoding="utf-8") == "ok"
    assert not (target / "tests").exists()
    assert (target_github / "workflows" / "release.yml").read_text(encoding="utf-8") == "old"


def test_copy_application_exclude_contains_github():
    assert ".github" in COPY_APPLICATION_EXCLUDE
    assert "tests" in COPY_APPLICATION_EXCLUDE
