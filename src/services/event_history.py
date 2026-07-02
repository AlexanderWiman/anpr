from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4


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
    """In-memory ring buffer of recent ANPR events for the web dashboard."""

    def __init__(self, max_size: int = 100) -> None:
        self._entries: deque[HistoryEntry] = deque(maxlen=max_size)
        self._lock = Lock()

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
            captured_at=captured_at,
            error=error,
        )
        with self._lock:
            self._entries.appendleft(entry)
        return entry.id

    def update_status(self, entry_id: str, status: str, error: str | None = None) -> None:
        with self._lock:
            for entry in self._entries:
                if entry.id == entry_id:
                    entry.status = status
                    entry.error = error
                    entry.recorded_at = datetime.now(timezone.utc)
                    break

    def list_recent(self, limit: int = 50) -> list[dict]:
        with self._lock:
            items = list(self._entries)[:limit]
        return [
            {
                "id": e.id,
                "plate": e.plate,
                "confidence": e.confidence,
                "provider": e.provider,
                "siteId": e.site_id,
                "cameraId": e.camera_id,
                "direction": e.direction,
                "status": e.status,
                "capturedAt": e.captured_at.astimezone(timezone.utc).isoformat(),
                "recordedAt": e.recorded_at.astimezone(timezone.utc).isoformat(),
                "error": e.error,
            }
            for e in items
        ]
