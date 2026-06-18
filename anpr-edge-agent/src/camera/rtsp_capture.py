import asyncio
from datetime import datetime, timezone
from pathlib import Path

import cv2

from src.camera.frame_io import frame_filename, save_frame

from src.camera.base import CameraStatus, FrameCaptureService
from src.config.settings import Settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RTSPCaptureService(FrameCaptureService):
    """
    Captures frames from an RTSP stream with automatic reconnect.

    Uses OpenCV VideoCapture with FFmpeg backend.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._capture: cv2.VideoCapture | None = None
        self._status = CameraStatus.DISCONNECTED
        self._last_frame_at: datetime | None = None
        self._frames_captured = 0
        self._lock = asyncio.Lock()

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

    def _open_capture(self) -> cv2.VideoCapture:
        url = self._settings.camera_rtsp_url
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    async def connect(self) -> bool:
        async with self._lock:
            self._status = CameraStatus.CONNECTING
            logger.info(
                "connecting to camera",
                extra={"event": "camera_connecting", "rtsp_url": self._redact_url()},
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
                logger.error(
                    "camera connection timeout",
                    extra={
                        "event": "camera_error",
                        "timeout_ms": self._settings.rtsp_connect_timeout_ms,
                    },
                )
                return False

            if not cap.isOpened():
                self._status = CameraStatus.ERROR
                logger.error(
                    "camera connection failed",
                    extra={"event": "camera_error", "reason": "stream not opened"},
                )
                return False

            ret, _ = await loop.run_in_executor(None, cap.read)
            if not ret:
                cap.release()
                self._status = CameraStatus.ERROR
                logger.error(
                    "camera connection failed",
                    extra={"event": "camera_error", "reason": "no frame received"},
                )
                return False

            if self._capture is not None:
                self._capture.release()

            self._capture = cap
            self._status = CameraStatus.CONNECTED
            logger.info(
                "camera connected",
                extra={"event": "camera_connected", "rtsp_url": self._redact_url()},
            )
            return True

    async def disconnect(self) -> None:
        async with self._lock:
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            self._status = CameraStatus.DISCONNECTED
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
                logger.warning(
                    "frame read timeout",
                    extra={"event": "camera_error", "reason": "read timeout"},
                )
                self._status = CameraStatus.RECONNECTING
                return None

            if not ret or frame is None:
                logger.warning(
                    "frame read failed",
                    extra={"event": "camera_error", "reason": "empty frame"},
                )
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

            self._last_frame_at = datetime.now(timezone.utc)
            self._frames_captured += 1
            logger.debug(
                "frame captured",
                extra={
                    "event": "frame_captured",
                    "path": str(frame_path),
                    "frame_number": self._frames_captured,
                },
            )
            return frame_path

    async def ensure_connected(self) -> bool:
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
        url = self._settings.camera_rtsp_url or ""
        if "@" in url:
            scheme, rest = url.split("://", 1)
            if "@" in rest:
                _, host_part = rest.rsplit("@", 1)
                return f"{scheme}://***@{host_part}"
        return url
