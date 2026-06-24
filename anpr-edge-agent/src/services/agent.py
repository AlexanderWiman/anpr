import asyncio
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

import uvicorn

from src.camera.factory import create_capture_service
from src.config.settings import Settings
from src.models.event import AnprEvent
from src.providers.factory import create_plate_provider
from src.queue.deduplicator import PlateDeduplicator
from src.queue.plate_confirmation import FramePlateBuffer
from src.queue.event_queue import EventQueue
from src.services.agent_controller import AgentController
from src.services.backend_client import BackendClient
from src.services.booking_hints import BookingHintService
from src.services.delivery import DeliveryService
from src.services.event_history import EventHistory
from src.services.heartbeat import HeartbeatService
from src.services.web_app import create_web_app
from src.utils.frame_cleanup import cleanup_frames
from src.utils.logging import get_logger, setup_logging
from src.utils.motion_gate import MotionGate
from src.utils.plates import normalize_plate

logger = get_logger(__name__)


class AnprAgent:
    """
    Main orchestrator for the ANPR edge agent.

    Coordinates RTSP capture, YOLO+OCR, deduplication, and event delivery.
    Web UI stays up; capture is controlled via AgentController (start/stop).
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._process_started_at = datetime.now(timezone.utc)

        settings.frames_dir.mkdir(parents=True, exist_ok=True)
        settings.events_dir.mkdir(parents=True, exist_ok=True)
        settings.log_dir.mkdir(parents=True, exist_ok=True)

        self.camera = create_capture_service(settings)
        self._backend = BackendClient(settings)
        self.booking_hints = BookingHintService(
            self._backend,
            enabled=settings.booking_hints_enabled,
            refresh_seconds=settings.booking_hints_refresh_seconds,
        )
        self._provider = create_plate_provider(settings, booking_hints=self.booking_hints)
        self.deduplicator = PlateDeduplicator(settings)
        self._plate_confirmation = FramePlateBuffer(window_size=3, min_hits=2)
        self._queue = EventQueue(settings.queue_file)
        self.history = EventHistory(max_size=settings.web_history_size)
        self.delivery = DeliveryService(
            settings, self._backend, self._queue, event_history=self.history
        )
        self.controller = AgentController(self)
        self.heartbeat = HeartbeatService(self, self._process_started_at)
        self._ocr_busy = False
        self._pending_frame: Path | None = None
        self._ocr_worker_running = False
        self._motion_gate = (
            MotionGate(
                threshold=settings.motion_threshold,
                active_seconds=settings.motion_active_seconds,
            )
            if settings.motion_gate_enabled
            else None
        )
        self._cleanup_task: asyncio.Task | None = None

    def get_capture_interval_ms(self) -> int:
        settings = self.settings
        if self._motion_gate is not None and self._motion_gate.is_active:
            return settings.frame_interval_ms
        if self._motion_gate is not None:
            return settings.motion_scan_interval_ms
        return settings.frame_interval_ms

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def queue(self) -> EventQueue:
        return self._queue

    @property
    def backend(self) -> BackendClient:
        return self._backend

    async def process_frame(self, frame_path: Path) -> bool:
        """Run plate detection on a captured frame and deliver events."""
        detections = await self._provider.detect_plate(str(frame_path))

        min_conf = min(self.settings.min_confidence, self.settings.ocr_min_confidence)

        if not detections:
            self._plate_confirmation.observe_empty()
            return False

        delivered = False
        for detection in detections:
            if detection.confidence < min_conf:
                logger.debug(
                    "detection below confidence threshold",
                    extra={
                        "event": "detection_filtered",
                        "plate": detection.plate,
                        "confidence": detection.confidence,
                        "min_confidence": min_conf,
                    },
                )
                continue

            normalized = normalize_plate(detection.plate)
            confirmed = self._plate_confirmation.observe(
                normalized, detection.confidence
            )
            if confirmed is None:
                continue

            confirmed_plate, confirmed_conf = confirmed
            self._plate_confirmation.mark_handled(confirmed_plate)

            if self._queue.has_pending_plate(confirmed_plate):
                continue

            if not self.deduplicator.should_accept(confirmed_plate, confirmed_conf):
                continue

            event = AnprEvent(
                site_id=self.settings.site_id,
                camera_id=self.settings.camera_id,
                plate=confirmed_plate,
                confidence=round(confirmed_conf, 4),
                captured_at=datetime.now(timezone.utc),
                provider=detection.provider,
                direction=self.settings.direction,
                snapshot_path=str(frame_path) if self.settings.save_snapshots else None,
            )

            history_id = self.history.record(
                plate=confirmed_plate,
                confidence=confirmed_conf,
                provider=detection.provider,
                site_id=self.settings.site_id,
                camera_id=self.settings.camera_id,
                direction=self.settings.direction,
                captured_at=event.captured_at,
                status="detected",
            )

            await self.delivery.submit(event, history_id=history_id)
            self.deduplicator.mark_submitted(confirmed_plate, confirmed_conf)
            delivered = True

        return delivered

    async def process_frame_background(self, frame_path: Path) -> None:
        """Queue latest frame for OCR — skip static scenes when motion gate is on."""
        if self._motion_gate is not None and not self._motion_gate.should_process(frame_path):
            frame_path.unlink(missing_ok=True)
            return

        if self._pending_frame and self._pending_frame.exists():
            self._pending_frame.unlink(missing_ok=True)

        self._pending_frame = frame_path

        if not self._ocr_worker_running:
            asyncio.create_task(self._ocr_worker(), name="ocr-worker")

    async def _run_frame_cleanup_once(self) -> None:
        settings = self.settings
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                cleanup_frames,
                settings.frames_dir,
                max_age_hours=settings.frame_retention_hours,
                max_files=settings.frame_max_files,
                max_storage_mb=settings.frame_max_storage_mb,
            ),
        )
        if result.deleted_count:
            logger.info(
                "frame storage cleaned",
                extra={
                    "event": "frame_cleanup",
                    "deleted": result.deleted_count,
                    "freed_mb": round(result.freed_bytes / (1024 * 1024), 2),
                    "remaining": result.remaining_count,
                    "remaining_mb": round(result.remaining_bytes / (1024 * 1024), 2),
                },
            )

    async def _frame_cleanup_loop(self) -> None:
        interval = max(60, self.settings.frame_cleanup_interval_sec)
        while True:
            try:
                await asyncio.sleep(interval)
                await self._run_frame_cleanup_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception(
                    "frame cleanup error",
                    extra={"event": "frame_cleanup_error", "error": str(exc)},
                )

    async def _ocr_worker(self) -> None:
        self._ocr_worker_running = True
        try:
            while self._pending_frame is not None:
                frame_path = self._pending_frame
                self._pending_frame = None
                self._ocr_busy = True
                try:
                    delivered = await self.process_frame(frame_path)
                except Exception as exc:
                    logger.exception(
                        "frame processing error",
                        extra={"event": "error", "error": str(exc), "path": str(frame_path)},
                    )
                    delivered = False
                finally:
                    keep = self.settings.save_snapshots and delivered
                    if not keep and frame_path.exists():
                        frame_path.unlink(missing_ok=True)
                    self._ocr_busy = False
        finally:
            self._ocr_worker_running = False

    async def run(self) -> None:
        """Start web dashboard and optionally auto-start ANPR capture."""
        logger.info(
            "process starting",
            extra={
                "event": "process_starting",
                "site_id": self.settings.site_id,
                "camera_id": self.settings.camera_id,
                "provider": self._provider.name,
                "auto_start": self.settings.agent_auto_start,
            },
        )

        web_app = create_web_app(self, self._process_started_at)
        config = uvicorn.Config(
            web_app,
            host=self.settings.health_host,
            port=self.settings.health_port,
            log_level="warning",
        )
        server = uvicorn.Server(config)

        display_host = (
            "localhost"
            if self.settings.health_host in ("0.0.0.0", "::")
            else self.settings.health_host
        )
        logger.info(
            "web dashboard starting",
            extra={
                "event": "web_ui_starting",
                "url": f"http://{display_host}:{self.settings.health_port}",
            },
        )

        async def _background_init() -> None:
            await self._run_frame_cleanup_once()
            self._cleanup_task = asyncio.create_task(
                self._frame_cleanup_loop(), name="frame-cleanup"
            )
            self.booking_hints.start_background_refresh()
            self.heartbeat.start()
            if self.settings.agent_auto_start:
                await self.controller.start()

        init_task = asyncio.create_task(_background_init(), name="agent-background-init")

        try:
            await server.serve()
        finally:
            init_task.cancel()
            await asyncio.gather(init_task, return_exceptions=True)
            if self._cleanup_task is not None:
                self._cleanup_task.cancel()
                await asyncio.gather(self._cleanup_task, return_exceptions=True)
            await self.booking_hints.stop()
            await self.heartbeat.stop()
            await self.controller.stop()
            await self._backend.close()
            logger.info("process stopped", extra={"event": "process_stopped"})


async def main() -> None:
    from src.config.settings import load_settings

    settings = load_settings()
    setup_logging(settings.log_dir, settings.log_level)
    agent = AnprAgent(settings)
    await agent.run()
