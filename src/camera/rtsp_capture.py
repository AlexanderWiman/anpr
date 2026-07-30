import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import time

from src.camera.frame_io import frame_filename, save_frame

from src.camera.base import CameraStatus, FrameCaptureService
from src.config.cameras import CameraConfig
from src.config.settings import Settings
from src.camera.status_messages import camera_status_message
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RTSPCaptureService(FrameCaptureService):
    """
    Captures frames from an RTSP stream with automatic reconnect.

    Uses OpenCV VideoCapture with FFmpeg backend.
    """

    def __init__(self, settings: Settings, camera: CameraConfig) -> None:
        self._settings = settings
        self._camera = camera
        self._capture: Any = None
        self._status = CameraStatus.DISCONNECTED
        self._last_frame_at: datetime | None = None
        self._frames_captured = 0
        self._last_error_reason: str | None = None
        self._consecutive_empty_frames = 0
        self._session_started_at: float | None = None
        self._on_reconnected: Callable[[], None] | None = None
        self._lock = asyncio.Lock()

    def set_on_reconnected(self, callback: Callable[[], None] | None) -> None:
        """Optional hook (e.g. re-arm motion gate after RTSP refresh)."""
        self._on_reconnected = callback

    @property
    def source_type(self) -> str:
        return "rtsp"

    @property
    def status(self) -> CameraStatus:
        return self._status

    @property
    def last_frame_at(self) -> datetime | None:
        return self._last_frame_at

    @property
    def frames_captured(self) -> int:
        return self._frames_captured

    @property
    def last_error_reason(self) -> str | None:
        return self._last_error_reason

    @property
    def status_message(self) -> str | None:
        return camera_status_message(
            status=self._status.value,
            reason=self._last_error_reason,
            rtsp_url=self._camera.rtsp_url,
            timeout_ms=self._settings.rtsp_connect_timeout_ms,
        )

    @property
    def camera_id(self) -> str:
        return self._camera.id

    @property
    def frames_dir(self) -> Path:
        return self._settings.frames_dir_for(self._camera.id)

    def _open_capture(self) -> Any:
        import os

        import cv2

        url = self._camera.rtsp_url
        transport = (self._settings.rtsp_transport or "tcp").strip().lower()
        if transport in ("tcp", "udp"):
            # Low-latency TCP options help flaky Tapo streams stay readable.
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                f"rtsp_transport;{transport}|fflags;nobuffer|max_delay;500000"
            )
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _set_error(self, reason: str) -> None:
        self._last_error_reason = reason

    def _clear_error(self) -> None:
        self._last_error_reason = None

    async def connect(self) -> bool:
        async with self._lock:
            self._status = CameraStatus.CONNECTING
            self._last_error_reason = "connecting"
            logger.info(
                "connecting to camera",
                extra={
                    "event": "camera_connecting",
                    "camera_id": self._camera.id,
                    "rtsp_url": self._redact_url(),
                },
            )

            loop = asyncio.get_event_loop()
            timeout_sec = self._settings.rtsp_connect_timeout_ms / 1000

            try:
                cap = await asyncio.wait_for(
                    loop.run_in_executor(None, self._open_capture),
                    timeout=timeout_sec,
                )
            except asyncio.TimeoutError:
                self._status = CameraStatus.ERROR
                self._set_error("connection_timeout")
                logger.error(
                    "camera connection timeout",
                    extra={
                        "event": "camera_error",
                        "reason": "connection_timeout",
                        "timeout_ms": self._settings.rtsp_connect_timeout_ms,
                    },
                )
                return False

            if not cap.isOpened():
                self._status = CameraStatus.ERROR
                self._set_error("stream_not_opened")
                logger.error(
                    "camera connection failed",
                    extra={"event": "camera_error", "reason": "stream_not_opened"},
                )
                return False

            ret, _ = await loop.run_in_executor(None, cap.read)
            if not ret:
                cap.release()
                self._status = CameraStatus.ERROR
                self._set_error("no_frame_received")
                logger.error(
                    "camera connection failed",
                    extra={"event": "camera_error", "reason": "no_frame_received"},
                )
                return False

            if self._capture is not None:
                self._capture.release()

            self._capture = cap
            self._status = CameraStatus.CONNECTED
            self._consecutive_empty_frames = 0
            self._session_started_at = time.monotonic()
            self._clear_error()
            logger.info(
                "camera connected",
                extra={
                    "event": "camera_connected",
                    "camera_id": self._camera.id,
                    "rtsp_url": self._redact_url(),
                },
            )
            if self._on_reconnected is not None:
                try:
                    self._on_reconnected()
                except Exception as exc:
                    logger.warning(
                        "on_reconnected callback failed",
                        extra={"event": "camera_error", "reason": str(exc)},
                    )
            return True

    async def disconnect(self) -> None:
        async with self._lock:
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            self._status = CameraStatus.DISCONNECTED
            self._clear_error()
            logger.info("camera disconnected", extra={"event": "camera_disconnected"})

    async def capture_frame(self, output_dir: Path) -> Path | None:
        if self._capture is None or not self._capture.isOpened():
            return None

        async with self._lock:
            loop = asyncio.get_event_loop()
            try:
                ret, frame = await asyncio.wait_for(
                    loop.run_in_executor(None, self._capture.read),
                    timeout=self._settings.rtsp_connect_timeout_ms / 1000,
                )
            except asyncio.TimeoutError:
                self._set_error("read_timeout")
                logger.warning(
                    "frame read timeout",
                    extra={"event": "camera_error", "reason": "read_timeout"},
                )
                self._status = CameraStatus.RECONNECTING
                return None

            if not ret or frame is None:
                self._consecutive_empty_frames += 1
                self._set_error("empty_frame")
                logger.warning(
                    "frame read failed",
                    extra={
                        "event": "camera_error",
                        "reason": "empty_frame",
                        "consecutive": self._consecutive_empty_frames,
                    },
                )
                # OpenCV can keep isOpened() true on a dead Tapo stream after the
                # first frame — force reconnect after empty reads.
                limit = max(1, self._settings.rtsp_empty_frame_reconnect)
                if (
                    self._capture is None
                    or not self._capture.isOpened()
                    or self._consecutive_empty_frames >= limit
                ):
                    if self._capture is not None:
                        self._capture.release()
                        self._capture = None
                    self._status = CameraStatus.RECONNECTING
                return None

            output_dir.mkdir(parents=True, exist_ok=True)
            filename = frame_filename("frame")
            frame_path = output_dir / filename

            success = await loop.run_in_executor(
                None, save_frame, str(frame_path), frame
            )
            if not success:
                logger.error(
                    "frame save failed",
                    extra={"event": "camera_error", "path": str(frame_path)},
                )
                return None

            write_camera_preview = __import__(
                "src.services.camera_preview", fromlist=["write_camera_preview"]
            ).write_camera_preview
            write_camera_preview(self._settings, self._camera.id, frame)

            self._last_frame_at = datetime.now(timezone.utc)
            self._frames_captured += 1
            self._consecutive_empty_frames = 0
            self._clear_error()
            logger.debug(
                "frame captured",
                extra={
                    "event": "frame_captured",
                    "camera_id": self._camera.id,
                    "path": str(frame_path),
                    "frame_number": self._frames_captured,
                },
            )
            return frame_path

    async def ensure_connected(self) -> bool:
        max_session = self._settings.rtsp_max_session_seconds
        if (
            max_session > 0
            and self._status == CameraStatus.CONNECTED
            and self._capture is not None
            and self._session_started_at is not None
            and time.monotonic() - self._session_started_at >= max_session
        ):
            logger.info(
                "refreshing RTSP session before stream dies",
                extra={
                    "event": "camera_session_refresh",
                    "camera_id": self._camera.id,
                    "max_session_seconds": max_session,
                },
            )
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            self._status = CameraStatus.RECONNECTING

        if self._status == CameraStatus.CONNECTED and self._capture is not None:
            if self._capture.isOpened():
                return True

        self._status = CameraStatus.RECONNECTING
        logger.info("reconnecting to camera", extra={"event": "camera_reconnecting"})

        if self._capture is not None:
            self._capture.release()
            self._capture = None

        delay = self._settings.rtsp_reconnect_delay_ms / 1000
        await asyncio.sleep(delay)
        return await self.connect()

    def _redact_url(self) -> str:
        url = self._camera.rtsp_url or ""
        if "@" in url:
            scheme, rest = url.split("://", 1)
            if "@" in rest:
                _, host_part = rest.rsplit("@", 1)
                return f"{scheme}://***@{host_part}"
        return url
