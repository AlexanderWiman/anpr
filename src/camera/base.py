from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path


class CameraStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class FrameCaptureService(ABC):
    """Abstract RTSP frame capture source."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Capture source identifier for health/logging."""

    @property
    @abstractmethod
    def status(self) -> CameraStatus:
        pass

    @property
    @abstractmethod
    def last_frame_at(self) -> datetime | None:
        pass

    @property
    @abstractmethod
    def frames_captured(self) -> int:
        pass

    @abstractmethod
    async def connect(self) -> bool:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def capture_frame(self, output_dir: Path) -> Path | None:
        pass

    @abstractmethod
    async def ensure_connected(self) -> bool:
        pass

    async def run_capture_loop(
        self,
        callback,
        interval_ms: Callable[[], int] | None = None,
    ) -> None:
        """Continuously capture frames at configured interval."""
        import asyncio

        from src.config.settings import Settings

        settings: Settings = getattr(self, "_settings")

        while True:
            if not await self.ensure_connected():
                await asyncio.sleep(settings.rtsp_reconnect_delay_ms / 1000)
                continue

            frame_path = await self.capture_frame(settings.frames_dir)
            if frame_path is None:
                await asyncio.sleep(settings.rtsp_reconnect_delay_ms / 1000)
                continue

            try:
                await callback(frame_path)
            except Exception as exc:
                from src.utils.logging import get_logger

                get_logger(__name__).exception(
                    "frame processing error",
                    extra={"event": "error", "error": str(exc)},
                )

            ms = interval_ms() if interval_ms else settings.frame_interval_ms
            await asyncio.sleep(max(ms, 100) / 1000)
