"""Cache today's expected registration numbers from backend for OCR disambiguation."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from src.services.backend_client import BackendClient
from src.utils.logging import get_logger
from src.utils.plates import normalize_plate, resolve_with_booking_hints

logger = get_logger(__name__)


class BookingHintService:
    """Keeps a local cache of plates booked today at this site."""

    def __init__(self, backend: BackendClient, *, enabled: bool, refresh_seconds: int) -> None:
        self._backend = backend
        self._enabled = enabled
        self._refresh_seconds = max(60, refresh_seconds)
        self._plates: frozenset[str] = frozenset()
        self._refreshed_at: datetime | None = None
        self._last_error: str | None = None
        self._refresh_lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def plate_count(self) -> int:
        return len(self._plates)

    @property
    def refreshed_at(self) -> datetime | None:
        return self._refreshed_at

    def status(self) -> dict:
        return {
            "enabled": self._enabled,
            "plateCount": self.plate_count,
            "refreshedAt": self._refreshed_at.isoformat() if self._refreshed_at else None,
            "lastError": self._last_error,
        }

    async def refresh_if_stale(self, *, max_age_seconds: int = 30) -> None:
        """Refresh when cache is empty or older than max_age_seconds."""
        if not self._enabled:
            return

        now = datetime.now(timezone.utc)
        if self._refreshed_at is not None:
            age = (now - self._refreshed_at).total_seconds()
            if age < max_age_seconds:
                return

        async with self._refresh_lock:
            if self._refreshed_at is not None:
                age = (datetime.now(timezone.utc) - self._refreshed_at).total_seconds()
                if age < max_age_seconds:
                    return
            await self.refresh()

    async def refresh(self) -> None:
        if not self._enabled:
            return

        try:
            result = await self._backend.fetch_expected_plates()
            plates = frozenset(normalize_plate(p) for p in result.get("plates", []))
            self._plates = plates
            self._refreshed_at = datetime.now(timezone.utc)
            self._last_error = None
            logger.info(
                "booking hints refreshed",
                extra={
                    "event": "booking_hints_refreshed",
                    "count": len(plates),
                },
            )
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning(
                "booking hints refresh failed",
                extra={"event": "booking_hints_error", "error": str(exc)},
            )

    def resolve_candidates(
        self, candidates: list[tuple[str, float]]
    ) -> tuple[str, float] | None:
        if not self._enabled or not self._plates:
            return None
        return resolve_with_booking_hints(candidates, self._plates)

    async def run_refresh_loop(self) -> None:
        if not self._enabled:
            return

        await self.refresh()
        while True:
            await asyncio.sleep(self._refresh_seconds)
            await self.refresh()

    def start_background_refresh(self) -> None:
        if not self._enabled or self._task is not None:
            return
        self._task = asyncio.create_task(self.run_refresh_loop(), name="booking-hints")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
