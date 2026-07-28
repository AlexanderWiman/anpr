"""Persistent log of ANPR events successfully delivered to the CRM backend."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from src.models.event import AnprEvent
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DeliveryRecord:
    id: str
    plate: str
    confidence: float
    provider: str
    site_id: str
    camera_id: str
    direction: str
    captured_at: datetime
    delivered_at: datetime


class DeliveryLog:
    """Ring buffer of successful CRM deliveries."""

    def __init__(
        self,
        log_file: Path,
        *,
        max_size: int = 2000,
        retention_hours: float = 168.0,
    ) -> None:
        self._log_file = log_file
        self._max_size = max(1, max_size)
        self._retention_hours = max(0.0, retention_hours)
        self._entries: list[DeliveryRecord] = []
        self._lock = Lock()
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    @property
    def total_delivered(self) -> int:
        with self._lock:
            return len(self._entries)

    def record(self, event: AnprEvent, *, delivered_at: datetime | None = None) -> str:
        now = delivered_at or datetime.now(timezone.utc)
        entry = DeliveryRecord(
            id=str(uuid4()),
            plate=event.plate,
            confidence=event.confidence,
            provider=event.provider,
            site_id=event.site_id,
            camera_id=event.camera_id,
            direction=event.direction,
            captured_at=_ensure_utc(event.captured_at),
            delivered_at=_ensure_utc(now),
        )
        with self._lock:
            self._entries.insert(0, entry)
            self._entries = self._prune(self._entries)
            if len(self._entries) > self._max_size:
                self._entries = self._entries[: self._max_size]
            self._persist_locked()
        return entry.id

    def list_recent(self, limit: int = 200) -> list[dict]:
        with self._lock:
            items = self._entries[:limit]
        return [_record_to_dict(entry) for entry in items]

    def _load(self) -> None:
        if not self._log_file.is_file():
            return
        try:
            raw = json.loads(self._log_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning(
                "delivery log load failed",
                extra={"event": "delivery_log_load_failed", "error": str(exc)},
            )
            return
        if not isinstance(raw, list):
            return

        loaded: list[DeliveryRecord] = []
        for item in raw:
            try:
                loaded.append(_record_from_dict(item))
            except (TypeError, ValueError):
                continue

        loaded.sort(key=lambda entry: entry.delivered_at, reverse=True)
        self._entries = self._prune(loaded)[: self._max_size]
        logger.info(
            "delivery log loaded",
            extra={"event": "delivery_log_loaded", "count": len(self._entries)},
        )

    def _prune(self, entries: list[DeliveryRecord]) -> list[DeliveryRecord]:
        if self._retention_hours <= 0:
            return entries
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self._retention_hours)
        return [entry for entry in entries if entry.delivered_at >= cutoff]

    def _persist_locked(self) -> None:
        payload = [_record_to_dict(entry) for entry in self._entries]
        self._log_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        raise ValueError("missing datetime")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _ensure_utc(parsed)


def _record_to_dict(entry: DeliveryRecord) -> dict:
    return {
        "id": entry.id,
        "plate": entry.plate,
        "confidence": entry.confidence,
        "provider": entry.provider,
        "siteId": entry.site_id,
        "cameraId": entry.camera_id,
        "direction": entry.direction,
        "capturedAt": entry.captured_at.astimezone(timezone.utc).isoformat(),
        "deliveredAt": entry.delivered_at.astimezone(timezone.utc).isoformat(),
        "status": "delivered",
    }


def _record_from_dict(data: dict) -> DeliveryRecord:
    return DeliveryRecord(
        id=str(data["id"]),
        plate=str(data["plate"]),
        confidence=float(data["confidence"]),
        provider=str(data.get("provider") or ""),
        site_id=str(data.get("siteId") or data.get("site_id") or ""),
        camera_id=str(data.get("cameraId") or data.get("camera_id") or ""),
        direction=str(data.get("direction") or ""),
        captured_at=_parse_datetime(data.get("capturedAt") or data.get("captured_at")),
        delivered_at=_parse_datetime(data.get("deliveredAt") or data.get("delivered_at")),
    )
