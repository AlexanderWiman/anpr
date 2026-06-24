"""Periodic status reports to backend for remote monitoring."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.services.status_report import build_status_report
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.services.agent import AnprAgent

logger = get_logger(__name__)


class HeartbeatService:
    """POST agent health snapshot to backend on a fixed interval."""

    def __init__(self, agent: AnprAgent, process_started_at: datetime) -> None:
        self._agent = agent
        self._process_started_at = process_started_at
        self._task: asyncio.Task | None = None
        self._last_sent_at: datetime | None = None
        self._last_error: str | None = None

    def status(self) -> dict:
        settings = self._agent.settings
        return {
            "enabled": settings.heartbeat_enabled,
            "intervalSeconds": settings.heartbeat_interval_seconds,
            "lastSentAt": self._last_sent_at.isoformat() if self._last_sent_at else None,
            "lastError": self._last_error,
        }

    def build_payload(self) -> dict:
        return build_status_report(self._agent, self._process_started_at)

    async def send_once(self) -> bool:
        if not self._agent.settings.heartbeat_enabled:
            return False

        await self._agent.delivery.refresh_backend_status()
        payload = self.build_payload()
        try:
            await self._agent.backend.send_heartbeat(payload)
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning(
                "heartbeat failed",
                extra={"event": "heartbeat_failed", "error": str(exc)},
            )
            return False

        self._last_sent_at = datetime.now(timezone.utc)
        self._last_error = None
        logger.debug(
            "heartbeat sent",
            extra={
                "event": "heartbeat_sent",
                "site_id": self._agent.settings.site_id,
                "agent_state": payload.get("agent", {}).get("state"),
                "camera_status": payload.get("camera", {}).get("status"),
            },
        )
        return True

    async def run_loop(self) -> None:
        settings = self._agent.settings
        interval = max(30, settings.heartbeat_interval_seconds)

        await asyncio.sleep(5)
        while True:
            await self.send_once()
            await asyncio.sleep(interval)

    def start(self) -> None:
        if not self._agent.settings.heartbeat_enabled or self._task is not None:
            return
        self._task = asyncio.create_task(self.run_loop(), name="heartbeat")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None
