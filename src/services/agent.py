import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

import uvicorn

from src.config.settings import Settings
from src.config.cameras import CameraConfig
from src.models.event import AnprEvent
from src.providers.factory import create_plate_provider
from src.queue.deduplicator import PlateDeduplicator
from src.queue.event_queue import EventQueue
from src.services.agent_controller import AgentController
from src.services.backend_client import BackendClient
from src.services.booking_hints import BookingHintService
from src.services.camera_pipeline import CameraPipeline
from src.services.delivery import DeliveryService
from src.services.event_history import EventHistory
from src.services.heartbeat import HeartbeatService
from src.services.remote_camera_config import RemoteCameraConfigService
from src.services.web_app import create_web_app
from src.utils.frame_cleanup import cleanup_frames
from src.utils.logging import get_logger, setup_logging
from src.utils.plates import normalize_plate

logger = get_logger(__name__)


@dataclass(frozen=True)
class PendingOcrFrame:
    camera_id: str
    frame_path: Path


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

        self.pipelines: dict[str, CameraPipeline] = {
            camera.id: CameraPipeline(settings, camera) for camera in settings.cameras
        }
        self._backend = BackendClient(settings)
        self.booking_hints = BookingHintService(
            self._backend,
            enabled=settings.booking_hints_enabled,
            refresh_seconds=settings.booking_hints_refresh_seconds,
        )
        self._provider = create_plate_provider(settings, booking_hints=self.booking_hints)
        self.deduplicator = PlateDeduplicator(settings)
        self._queue = EventQueue(settings.queue_file)
        self.history = EventHistory(max_size=settings.web_history_size)
        self.delivery = DeliveryService(
            settings, self._backend, self._queue, event_history=self.history
        )
        self.controller = AgentController(self)
        self.remote_camera_config = RemoteCameraConfigService(self)
        self.heartbeat = HeartbeatService(self, self._process_started_at)
        self._ocr_busy = False
        self._ocr_queue: deque[PendingOcrFrame] = deque()
        self._queued_frame_paths: dict[str, Path] = {}
        self._ocr_worker_running = False
        self._cleanup_task: asyncio.Task | None = None
        self._frame_captures_in_flight: set[str] = set()

    @property
    def camera(self):
        """Backward-compatible access to the primary camera capture service."""
        return self.primary_pipeline.capture

    @property
    def primary_pipeline(self) -> CameraPipeline | None:
        if not self.pipelines:
            return None
        return next(iter(self.pipelines.values()))

    def _sync_primary_camera_settings(self, cameras: list) -> None:
        if not cameras:
            return
        primary = cameras[0]
        object.__setattr__(self.settings, "cameras", cameras)
        object.__setattr__(self.settings, "camera_id", primary.id)
        object.__setattr__(self.settings, "direction", primary.direction)
        object.__setattr__(self.settings, "camera_rtsp_url", primary.rtsp_url)

    async def apply_camera_configs(self, cameras: list[CameraConfig]) -> None:
        """Replace in-memory camera pipelines (used by remote config polling)."""
        enabled = [camera for camera in cameras if camera.enabled]
        current_ids = set(self.pipelines.keys())
        next_ids = {camera.id for camera in enabled}

        for camera_id in current_ids - next_ids:
            pipeline = self.pipelines.pop(camera_id)
            await pipeline.capture.disconnect()

        for camera in enabled:
            existing = self.pipelines.get(camera.id)
            if existing is None or existing.config.rtsp_url != camera.rtsp_url:
                if existing is not None:
                    await existing.capture.disconnect()
                self.pipelines[camera.id] = CameraPipeline(self.settings, camera)
            else:
                existing.config = camera

        self._sync_primary_camera_settings(enabled)
        await self.controller.reconcile_capture_loops()

    def pipeline_for(self, camera_id: str) -> CameraPipeline:
        pipeline = self.pipelines.get(camera_id)
        if pipeline is None:
            raise KeyError(f"Unknown camera_id: {camera_id}")
        return pipeline

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def queue(self) -> EventQueue:
        return self._queue

    @property
    def backend(self) -> BackendClient:
        return self._backend

    async def perform_remote_frame_capture(self, request_id: str) -> None:
        if request_id in self._frame_captures_in_flight:
            return

        self._frame_captures_in_flight.add(request_id)
        try:
            from src.services.frame_capture import capture_rtsp_jpeg_base64

            loop = asyncio.get_event_loop()
            image_b64, width, height = await loop.run_in_executor(
                None,
                lambda: capture_rtsp_jpeg_base64(self.settings),
            )
            captured_at = datetime.now(timezone.utc).isoformat()
            await self.backend.upload_frame_capture(
                request_id,
                status="completed",
                image_base64=image_b64,
                width=width,
                height=height,
                captured_at=captured_at,
            )
            logger.info(
                "remote frame capture uploaded",
                extra={
                    "event": "frame_capture_uploaded",
                    "request_id": request_id,
                    "width": width,
                    "height": height,
                },
            )
        except Exception as exc:
            logger.warning(
                "remote frame capture failed",
                extra={
                    "event": "frame_capture_failed",
                    "request_id": request_id,
                    "error": str(exc),
                },
            )
            try:
                await self.backend.upload_frame_capture(
                    request_id,
                    status="failed",
                    error=str(exc),
                )
            except Exception as upload_exc:
                logger.warning(
                    "frame capture failure upload failed",
                    extra={
                        "event": "frame_capture_failed",
                        "request_id": request_id,
                        "error": str(upload_exc),
                    },
                )
        finally:
            self._frame_captures_in_flight.discard(request_id)

    async def process_frame(self, frame_path: Path, camera_id: str) -> bool:
        """Run plate detection on a captured frame and deliver events."""
        pipeline = self.pipeline_for(camera_id)
        detections = await self._provider.detect_plate(str(frame_path))

        min_conf = min(self.settings.min_confidence, self.settings.ocr_min_confidence)

        if not detections:
            pipeline.plate_confirmation.observe_empty()
            return False

        delivered = False
        for detection in detections:
            if detection.confidence < min_conf:
                logger.debug(
                    "detection below confidence threshold",
                    extra={
                        "event": "detection_filtered",
                        "camera_id": camera_id,
                        "plate": detection.plate,
                        "confidence": detection.confidence,
                        "min_confidence": min_conf,
                    },
                )
                continue

            normalized = normalize_plate(detection.plate)
            confirmed = pipeline.plate_confirmation.observe(
                normalized, detection.confidence
            )
            if confirmed is None:
                continue

            confirmed_plate, confirmed_conf = confirmed
            pipeline.plate_confirmation.mark_handled(confirmed_plate)

            if self._queue.has_pending_plate(confirmed_plate):
                continue

            if not self.deduplicator.should_accept(confirmed_plate, confirmed_conf):
                continue

            event = AnprEvent(
                site_id=self.settings.site_id,
                camera_id=camera_id,
                plate=confirmed_plate,
                confidence=round(confirmed_conf, 4),
                captured_at=datetime.now(timezone.utc),
                provider=detection.provider,
                direction=pipeline.direction,
                snapshot_path=str(frame_path) if self.settings.save_snapshots else None,
            )

            history_id = self.history.record(
                plate=confirmed_plate,
                confidence=confirmed_conf,
                provider=detection.provider,
                site_id=self.settings.site_id,
                camera_id=camera_id,
                direction=pipeline.direction,
                captured_at=event.captured_at,
                status="detected",
            )

            await self.delivery.submit(event, history_id=history_id)
            self.deduplicator.mark_submitted(confirmed_plate, confirmed_conf)
            delivered = True

        return delivered

    async def process_frame_background(self, frame_path: Path, camera_id: str) -> None:
        """Queue latest frame for OCR — skip static scenes when motion gate is on."""
        pipeline = self.pipeline_for(camera_id)
        if not pipeline.should_process_frame(frame_path):
            frame_path.unlink(missing_ok=True)
            return

        stale_path = self._queued_frame_paths.get(camera_id)
        if stale_path and stale_path.exists():
            stale_path.unlink(missing_ok=True)

        self._queued_frame_paths[camera_id] = frame_path
        self._ocr_queue = deque(
            item for item in self._ocr_queue if item.camera_id != camera_id
        )
        self._ocr_queue.append(PendingOcrFrame(camera_id=camera_id, frame_path=frame_path))

        if not self._ocr_worker_running:
            asyncio.create_task(self._ocr_worker(), name="ocr-worker")

    async def _run_frame_cleanup_once(self) -> None:
        settings = self.settings
        loop = asyncio.get_event_loop()
        total_deleted = 0
        total_freed = 0
        total_remaining = 0
        total_remaining_bytes = 0

        cleanup_dirs = {pipeline.frames_dir for pipeline in self.pipelines.values()}
        if not settings.is_multi_camera:
            cleanup_dirs.add(settings.frames_dir)

        for frames_dir in cleanup_dirs:
            result = await loop.run_in_executor(
                None,
                partial(
                    cleanup_frames,
                    frames_dir,
                    max_age_hours=settings.frame_retention_hours,
                    max_files=settings.frame_max_files,
                    max_storage_mb=settings.frame_max_storage_mb,
                ),
            )
            total_deleted += result.deleted_count
            total_freed += result.freed_bytes
            total_remaining += result.remaining_count
            total_remaining_bytes += result.remaining_bytes

        if total_deleted:
            logger.info(
                "frame storage cleaned",
                extra={
                    "event": "frame_cleanup",
                    "deleted": total_deleted,
                    "freed_mb": round(total_freed / (1024 * 1024), 2),
                    "remaining": total_remaining,
                    "remaining_mb": round(total_remaining_bytes / (1024 * 1024), 2),
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
            while self._ocr_queue:
                pending = self._ocr_queue.popleft()
                frame_path = pending.frame_path
                camera_id = pending.camera_id
                self._queued_frame_paths.pop(camera_id, None)
                self._ocr_busy = True
                try:
                    delivered = await self.process_frame(frame_path, camera_id)
                except Exception as exc:
                    logger.exception(
                        "frame processing error",
                        extra={
                            "event": "error",
                            "camera_id": camera_id,
                            "error": str(exc),
                            "path": str(frame_path),
                        },
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
        camera_ids = [camera.id for camera in self.settings.cameras]
        logger.info(
            "process starting",
            extra={
                "event": "process_starting",
                "site_id": self.settings.site_id,
                "camera_ids": camera_ids,
                "camera_count": len(camera_ids),
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
            self.remote_camera_config.start()
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
            await self.remote_camera_config.stop()
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
