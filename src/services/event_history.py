from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
from threading import Lock
from uuid import uuid4

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class HistoryEntry:
    id: str
    plate: str
    confidence: float
    provider: str
    site_id: str
    camera_id: str
    direction: str
    status: str  # detected | delivered | queued | failed
    captured_at: datetime
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None


class EventHistory:
    """Recent ANPR events for the web dashboard, persisted across restarts."""

    def __init__(
        self,
        max_size: int = 100,
        *,
        history_file: Path | None = None,
        retention_hours: float = 48.0,
    ) -> None:
        self._max_size = max(1, max_size)
        self._history_file = history_file
        self._retention_hours = max(0.0, retention_hours)
        self._entries: deque[HistoryEntry] = deque(maxlen=self._max_size)
        self._lock = Lock()
        if self._history_file is not None:
            self._history_file.parent.mkdir(parents=True, exist_ok=True)
            self._load()

    def record(
        self,
        *,
        plate: str,
        confidence: float,
        provider: str,
        site_id: str,
        camera_id: str,
        direction: str,
        captured_at: datetime,
        status: str,
        error: str | None = None,
        entry_id: str | None = None,
    ) -> str:
        entry = HistoryEntry(
            id=entry_id or str(uuid4()),
            plate=plate,
            confidence=confidence,
            provider=provider,
            site_id=site_id,
            camera_id=camera_id,
            direction=direction,
            status=status,
            captured_at=_ensure_utc(captured_at),
            error=error,
        )
        with self._lock:
            self._entries.appendleft(entry)
            self._persist_locked()
        return entry.id

    def update_status(self, entry_id: str, status: str, error: str | None = None) -> None:
        with self._lock:
            for entry in self._entries:
                if entry.id == entry_id:
                    entry.status = status
                    entry.error = error
                    entry.recorded_at = datetime.now(timezone.utc)
                    break
            self._persist_locked()

    def list_recent(self, limit: int = 50) -> list[dict]:
        with self._lock:
            items = list(self._entries)[:limit]
        return [_entry_to_dict(entry) for entry in items]

    def _load(self) -> None:
        if self._history_file is None or not self._history_file.is_file():
            return

        try:
            raw = json.loads(self._history_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning(
                "event history load failed",
                extra={"event": "event_history_load_failed", "error": str(exc)},
            )
            return

        if not isinstance(raw, list):
            return

        now = datetime.now(timezone.utc)
        loaded: list[HistoryEntry] = []
        for item in raw:
            try:
                loaded.append(_entry_from_dict(item))
            except (TypeError, ValueError):
                continue

        kept = _prune_entries(loaded, self._retention_hours, now)
        kept.sort(key=lambda entry: entry.captured_at, reverse=True)
        self._entries = deque(kept[: self._max_size], maxlen=self._max_size)
        logger.info(
            "event history loaded",
            extra={"event": "event_history_loaded", "count": len(self._entries)},
        )

    def _persist_locked(self) -> None:
        if self._history_file is None:
            return

        now = datetime.now(timezone.utc)
        kept = _prune_entries(list(self._entries), self._retention_hours, now)
        payload = [_entry_to_dict(entry) for entry in kept[: self._max_size]]
        self._history_file.write_text(
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


def _entry_to_dict(entry: HistoryEntry) -> dict:
    return {
        "id": entry.id,
        "plate": entry.plate,
        "confidence": entry.confidence,
        "provider": entry.provider,
        "siteId": entry.site_id,
        "cameraId": entry.camera_id,
        "direction": entry.direction,
        "status": entry.status,
        "capturedAt": entry.captured_at.astimezone(timezone.utc).isoformat(),
        "recordedAt": entry.recorded_at.astimezone(timezone.utc).isoformat(),
        "error": entry.error,
    }


def _entry_from_dict(data: dict) -> HistoryEntry:
    return HistoryEntry(
        id=str(data["id"]),
        plate=str(data["plate"]),
        confidence=float(data["confidence"]),
        provider=str(data.get("provider") or ""),
        site_id=str(data.get("siteId") or data.get("site_id") or ""),
        camera_id=str(data.get("cameraId") or data.get("camera_id") or ""),
        direction=str(data.get("direction") or ""),
        status=str(data["status"]),
        captured_at=_parse_datetime(data.get("capturedAt") or data.get("captured_at")),
        recorded_at=_parse_datetime(data.get("recordedAt") or data.get("recorded_at")),
        error=data.get("error"),
    )


def _prune_entries(
    entries: list[HistoryEntry],
    retention_hours: float,
    now: datetime,
) -> list[HistoryEntry]:
    if retention_hours <= 0:
        return entries
    cutoff = now - timedelta(hours=retention_hours)
    return [entry for entry in entries if entry.captured_at >= cutoff]
