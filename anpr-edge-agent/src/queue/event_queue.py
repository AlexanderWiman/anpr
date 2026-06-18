import json
from datetime import datetime, timezone
from pathlib import Path

from src.models.event import QueuedEvent
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EventQueue:
    """
    Persistent offline queue for ANPR events.

    Stores pending/failed events as JSON on disk for crash recovery.
    """

    def __init__(self, queue_file: Path) -> None:
        self._queue_file = queue_file
        self._queue_file.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[QueuedEvent] = []
        self._load()

    @property
    def size(self) -> int:
        return len(self._events)

    def _load(self) -> None:
        if not self._queue_file.exists():
            self._events = []
            return

        try:
            raw = json.loads(self._queue_file.read_text(encoding="utf-8"))
            self._events = [QueuedEvent.model_validate(item) for item in raw]
            logger.info(
                "queue loaded",
                extra={"event": "queue_loaded", "size": len(self._events)},
            )
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(
                "queue load failed",
                extra={"event": "error", "error": str(exc)},
            )
            self._events = []

    def _persist(self) -> None:
        data = [event.model_dump(mode="json") for event in self._events]
        self._queue_file.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )

    def has_pending_plate(self, plate: str) -> bool:
        normalized = plate.upper().strip()
        return any(
            item.event.plate.upper().strip() == normalized for item in self._events
        )

    def enqueue(self, event: QueuedEvent) -> None:
        if self.has_pending_plate(event.event.plate):
            logger.info(
                "duplicate queue skipped",
                extra={
                    "event": "queue_duplicate_skipped",
                    "plate": event.event.plate,
                },
            )
            return
        self._events.append(event)
        self._persist()
        logger.info(
            "event queued",
            extra={
                "event": "event_queued",
                "queue_id": event.id,
                "plate": event.event.plate,
                "queue_size": self.size,
            },
        )

    def dequeue(self, event_id: str) -> None:
        self._events = [e for e in self._events if e.id != event_id]
        self._persist()

    def get_ready_events(self) -> list[QueuedEvent]:
        now = datetime.now(timezone.utc)
        ready = []
        for item in self._events:
            if item.next_retry_at is None or item.next_retry_at <= now:
                ready.append(item)
        return ready

    def update(self, event: QueuedEvent) -> None:
        for i, existing in enumerate(self._events):
            if existing.id == event.id:
                self._events[i] = event
                break
        self._persist()

    def all_events(self) -> list[QueuedEvent]:
        return list(self._events)
