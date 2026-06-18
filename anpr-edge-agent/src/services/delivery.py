import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from src.config.settings import Settings
from src.models.event import AnprEvent, QueuedEvent
from src.queue.event_queue import EventQueue
from src.services.backend_client import BackendClient
from src.services.event_history import EventHistory
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DeliveryService:
    """
    Delivers ANPR events to backend with retry and offline queue.

    Uses exponential backoff for failed deliveries.
    """

    def __init__(
        self,
        settings: Settings,
        backend: BackendClient,
        queue: EventQueue,
        event_history: EventHistory | None = None,
    ) -> None:
        self._settings = settings
        self._backend = backend
        self._queue = queue
        self._history = event_history
        self._backend_reachable = False
        self._deliveries_succeeded = 0
        self._deliveries_failed = 0

    @property
    def backend_reachable(self) -> bool:
        return self._backend_reachable

    @property
    def queue_size(self) -> int:
        return self._queue.size

    @property
    def stats(self) -> dict:
        return {
            "deliveries_succeeded": self._deliveries_succeeded,
            "deliveries_failed": self._deliveries_failed,
            "queue_size": self._queue.size,
            "backend_reachable": self._backend_reachable,
        }

    async def submit(self, event: AnprEvent, history_id: str | None = None) -> bool:
        """Attempt immediate delivery; queue on failure. Returns True if delivered."""
        if self._queue.has_pending_plate(event.plate):
            if self._history and history_id:
                self._history.update_status(
                    history_id, "queued", "already pending delivery"
                )
            return False

        queued = QueuedEvent(event=event, history_id=history_id)
        success = await self._try_deliver(queued)
        if success:
            if self._history and history_id:
                self._history.update_status(history_id, "delivered")
            return True

        self._queue.enqueue(queued)
        if self._history and history_id:
            self._history.update_status(history_id, "queued", queued.last_error)
        return False

    async def _try_deliver(self, queued: QueuedEvent) -> bool:
        queued.attempts += 1
        queued.last_attempt_at = datetime.now(timezone.utc)

        try:
            await self._backend.send_anpr_event(queued.event)
            self._backend_reachable = True
            self._deliveries_succeeded += 1
            return True
        except httpx.HTTPError as exc:
            self._backend_reachable = False
            self._deliveries_failed += 1
            queued.last_error = str(exc)

            delay = self._calculate_backoff(queued.attempts)
            queued.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

            logger.warning(
                "delivery failed",
                extra={
                    "event": "delivery_failed",
                    "plate": queued.event.plate,
                    "attempt": queued.attempts,
                    "error": str(exc),
                    "retry_in_seconds": delay,
                },
            )
            logger.info(
                "retry scheduled",
                extra={
                    "event": "retry_scheduled",
                    "queue_id": queued.id,
                    "attempt": queued.attempts,
                    "next_retry_at": queued.next_retry_at.isoformat(),
                },
            )
            return False

    def _calculate_backoff(self, attempt: int) -> float:
        base = self._settings.backend_retry_base_delay_seconds
        max_delay = 300.0  # cap at 5 minutes
        delay = base * (2 ** (attempt - 1))
        return min(delay, max_delay)

    def _update_history(
        self,
        queued: QueuedEvent,
        status: str,
        error: str | None = None,
    ) -> None:
        if not self._history:
            return
        if queued.history_id:
            self._history.update_status(queued.history_id, status, error)
        else:
            self._history.record(
                plate=queued.event.plate,
                confidence=queued.event.confidence,
                provider=queued.event.provider,
                site_id=queued.event.site_id,
                camera_id=queued.event.camera_id,
                direction=queued.event.direction,
                captured_at=queued.event.captured_at,
                status=status,
                error=error,
            )

    async def run_retry_loop(self) -> None:
        """Background loop that retries queued events."""
        while True:
            try:
                self._backend_reachable = await self._backend.healthcheck()
            except Exception:
                self._backend_reachable = False

            ready = self._queue.get_ready_events()
            for queued in ready:
                if queued.attempts >= self._settings.backend_max_retries:
                    logger.error(
                        "event permanently failed",
                        extra={
                            "event": "delivery_failed",
                            "queue_id": queued.id,
                            "plate": queued.event.plate,
                            "attempts": queued.attempts,
                            "last_error": queued.last_error,
                        },
                    )
                    self._queue.dequeue(queued.id)
                    self._update_history(queued, "failed", queued.last_error)
                    continue

                success = await self._try_deliver(queued)
                if success:
                    self._queue.dequeue(queued.id)
                    self._update_history(queued, "delivered")
                else:
                    self._queue.update(queued)
                    if queued.attempts >= self._settings.backend_max_retries:
                        self._update_history(queued, "failed", queued.last_error)

            await asyncio.sleep(5)
