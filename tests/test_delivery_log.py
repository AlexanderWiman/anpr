import json
from datetime import datetime, timedelta, timezone

from src.models.event import AnprEvent
from src.services.delivery_log import DeliveryLog


def _event(plate: str, *, captured: datetime | None = None) -> AnprEvent:
    return AnprEvent(
        site_id="borlange",
        camera_id="entrance-1",
        plate=plate,
        confidence=0.91,
        captured_at=captured or datetime(2026, 7, 28, 9, 15, tzinfo=timezone.utc),
        provider="yolo_ocr",
        direction="entry",
    )


def test_delivery_log_persists_and_reloads(tmp_path):
    log_file = tmp_path / "crm-deliveries.json"
    delivered_at = datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc)

    log = DeliveryLog(log_file, max_size=100, retention_hours=168)
    log.record(_event("ABC123"), delivered_at=delivered_at)

    assert log_file.is_file()
    reloaded = DeliveryLog(log_file, max_size=100, retention_hours=168)
    items = reloaded.list_recent(limit=10)

    assert len(items) == 1
    assert items[0]["plate"] == "ABC123"
    assert items[0]["status"] == "delivered"
    assert items[0]["deliveredAt"].startswith("2026-07-28T10:00:00")


def test_delivery_log_prunes_entries_older_than_retention(tmp_path):
    log_file = tmp_path / "crm-deliveries.json"
    now = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=200)

    log = DeliveryLog(log_file, max_size=100, retention_hours=168)
    log.record(_event("OLD111"), delivered_at=old)
    log.record(_event("NEW222"), delivered_at=now)

    payload = json.loads(log_file.read_text(encoding="utf-8"))
    plates = {item["plate"] for item in payload}
    assert "NEW222" in plates
    assert "OLD111" not in plates


def test_delivery_log_total_delivered_survives_reload(tmp_path):
    log_file = tmp_path / "crm-deliveries.json"
    log = DeliveryLog(log_file, max_size=100, retention_hours=168)
    log.record(_event("ONE111"))
    log.record(_event("TWO222"))

    reloaded = DeliveryLog(log_file, max_size=100, retention_hours=168)
    assert reloaded.total_delivered == 2
