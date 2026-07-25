import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.utils.log_export import build_log_export, collect_log_lines_since


def _write_log(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_collect_log_lines_since_filters_by_hours(tmp_path):
    log_dir = tmp_path / "logs"
    now = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)
    rows = [
        {"timestamp": "2026-07-24 11:00:00,000", "level": "INFO", "message": "old"},
        {"timestamp": "2026-07-25 11:30:00,000", "level": "INFO", "message": "recent"},
    ]
    _write_log(log_dir / "agent.log", rows)

    lines, meta = collect_log_lines_since(log_dir, hours=24, now=now)

    assert meta["matched"] == 1
    assert lines == [json.dumps(rows[1], ensure_ascii=False)]


def test_build_log_export_gzip_roundtrip(tmp_path):
    log_dir = tmp_path / "logs"
    now = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)
    rows = [
        {"timestamp": "2026-07-25 11:00:00,000", "level": "INFO", "message": "motion", "event": "motion_active"},
        {"timestamp": "2026-07-25 11:00:01,000", "level": "INFO", "message": "plate", "event": "plate_detected"},
    ]
    _write_log(log_dir / "agent.log", rows)

    bundle = build_log_export(log_dir, hours=24, now=now)

    assert bundle.line_count == 2
    assert bundle.compressed_bytes > 0
    assert bundle.content_gzip_base64
    payload = bundle.as_upload_payload("00000000-0000-4000-8000-000000000001")
    assert payload["status"] == "completed"
    assert payload["lineCount"] == 2


def test_build_log_export_truncates_large_payload(tmp_path):
    log_dir = tmp_path / "logs"
    now = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)
    rows = [
        {
            "timestamp": (now - timedelta(minutes=index)).strftime("%Y-%m-%d %H:%M:%S,000"),
            "level": "INFO",
            "message": f"line-{index}-" + ("abcdefghijklmnopqrstuvwxyz" * 20),
        }
        for index in range(400)
    ]
    _write_log(log_dir / "agent.log", rows)

    bundle = build_log_export(log_dir, hours=24, max_gzip_bytes=2000, now=now)

    assert bundle.truncated is True
    assert bundle.line_count < len(rows)
    assert bundle.compressed_bytes <= 2000
