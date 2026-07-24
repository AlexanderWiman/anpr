import json
from pathlib import Path

from src.utils.log_reader import read_recent_logs


def _write_log(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_read_recent_logs_returns_tail_in_order(tmp_path):
    log_dir = tmp_path / "logs"
    rows = [
        {"timestamp": "2026-07-24 07:00:00,000", "level": "INFO", "logger": "a", "message": "first"},
        {"timestamp": "2026-07-24 07:00:01,000", "level": "WARNING", "logger": "b", "message": "warn"},
        {"timestamp": "2026-07-24 07:00:02,000", "level": "ERROR", "logger": "c", "message": "fail"},
    ]
    _write_log(log_dir / "agent.log", rows)

    result = read_recent_logs(log_dir, tail=2)

    assert len(result["entries"]) == 2
    assert result["entries"][0]["message"] == "warn"
    assert result["entries"][1]["message"] == "fail"


def test_read_recent_logs_filters_by_level(tmp_path):
    log_dir = tmp_path / "logs"
    rows = [
        {"timestamp": "2026-07-24 07:00:00,000", "level": "INFO", "logger": "a", "message": "info"},
        {"timestamp": "2026-07-24 07:00:01,000", "level": "WARNING", "logger": "b", "message": "warn"},
        {"timestamp": "2026-07-24 07:00:02,000", "level": "ERROR", "logger": "c", "message": "fail"},
    ]
    _write_log(log_dir / "agent.log", rows)

    result = read_recent_logs(log_dir, tail=50, min_level="warning")

    assert [entry["level"] for entry in result["entries"]] == ["WARNING", "ERROR"]


def test_read_recent_logs_includes_startup_log(tmp_path):
    log_dir = tmp_path / "logs"
    _write_log(
        log_dir / "agent.log",
        [{"timestamp": "2026-07-24 07:00:00,000", "level": "INFO", "message": "agent"}],
    )
    _write_log(
        log_dir / "agent-startup.log",
        [{"timestamp": "2026-07-24 07:00:00,000", "level": "INFO", "message": "startup"}],
    )

    result = read_recent_logs(log_dir, tail=10, source="all")

    messages = [entry["message"] for entry in result["entries"]]
    assert "agent" in messages
    assert "startup" in messages
    assert len(result["files"]) == 2
