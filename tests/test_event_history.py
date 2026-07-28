import json
from datetime import datetime, timedelta, timezone

from src.services.event_history import EventHistory


def test_event_history_persists_and_reloads(tmp_path):
    history_file = tmp_path / "dashboard-history.json"
    captured = datetime(2026, 7, 28, 9, 15, tzinfo=timezone.utc)

    history = EventHistory(
        100,
        history_file=history_file,
        retention_hours=48,
    )
    history.record(
        plate="ABC123",
        confidence=0.91,
        provider="yolo_ocr",
        site_id="borlange",
        camera_id="entrance-1",
        direction="entry",
        captured_at=captured,
        status="delivered",
    )

    assert history_file.is_file()
    reloaded = EventHistory(100, history_file=history_file, retention_hours=48)
    items = reloaded.list_recent(limit=10)

    assert len(items) == 1
    assert items[0]["plate"] == "ABC123"
    assert items[0]["status"] == "delivered"


def test_event_history_prunes_entries_older_than_retention(tmp_path):
    history_file = tmp_path / "dashboard-history.json"
    now = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=72)

    history = EventHistory(100, history_file=history_file, retention_hours=48)
    history.record(
        plate="OLD111",
        confidence=0.8,
        provider="yolo_ocr",
        site_id="borlange",
        camera_id="entrance-1",
        direction="entry",
        captured_at=old,
        status="delivered",
    )
    history.record(
        plate="NEW222",
        confidence=0.9,
        provider="yolo_ocr",
        site_id="borlange",
        camera_id="entrance-1",
        direction="entry",
        captured_at=now,
        status="delivered",
    )

    payload = json.loads(history_file.read_text(encoding="utf-8"))
    plates = {item["plate"] for item in payload}
    assert "NEW222" in plates
    assert "OLD111" not in plates


def test_event_history_update_status_persists(tmp_path):
    history_file = tmp_path / "dashboard-history.json"
    history = EventHistory(100, history_file=history_file, retention_hours=48)
    entry_id = history.record(
        plate="XYZ789",
        confidence=0.75,
        provider="yolo_ocr",
        site_id="borlange",
        camera_id="entrance-1",
        direction="entry",
        captured_at=datetime.now(timezone.utc),
        status="detected",
    )
    history.update_status(entry_id, "delivered")

    reloaded = EventHistory(100, history_file=history_file, retention_hours=48)
    assert reloaded.list_recent()[0]["status"] == "delivered"
