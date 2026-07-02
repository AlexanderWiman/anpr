"""Per-camera capture and plate-confirmation state."""

from __future__ import annotations

from pathlib import Path

from src.camera.factory import create_capture_service
from src.camera.rtsp_capture import RTSPCaptureService
from src.config.cameras import CameraConfig
from src.config.settings import Settings
from src.queue.plate_confirmation import FramePlateBuffer
from src.utils.motion_gate import MotionGate


class CameraPipeline:
    """One hall/camera: RTSP capture, motion gate, and plate confirmation."""

    def __init__(self, settings: Settings, config: CameraConfig) -> None:
        self.settings = settings
        self.config = config
        self.capture: RTSPCaptureService = create_capture_service(settings, config)
        self.frames_dir = settings.frames_dir_for(config.id)
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.plate_confirmation = FramePlateBuffer(window_size=3, min_hits=2)

        motion_enabled = (
            config.motion_gate_enabled
            if config.motion_gate_enabled is not None
            else settings.motion_gate_enabled
        )
        self.motion_gate = (
            MotionGate(
                threshold=settings.motion_threshold,
                active_seconds=settings.motion_active_seconds,
            )
            if motion_enabled
            else None
        )

    @property
    def camera_id(self) -> str:
        return self.config.id

    @property
    def direction(self) -> str:
        return self.config.direction

    @property
    def label(self) -> str:
        return self.config.label or self.config.id

    def get_capture_interval_ms(self) -> int:
        settings = self.settings
        active_interval = self.config.frame_interval_ms or settings.frame_interval_ms
        scan_interval = settings.motion_scan_interval_ms

        if self.motion_gate is not None and self.motion_gate.is_active:
            return active_interval
        if self.motion_gate is not None:
            return scan_interval
        return active_interval

    def should_process_frame(self, frame_path: Path) -> bool:
        if self.motion_gate is None:
            return True
        return self.motion_gate.should_process(frame_path)

    def reset_runtime_state(self) -> None:
        if self.motion_gate is not None:
            self.motion_gate.reset()
            self.motion_gate.activate()
        self.plate_confirmation.clear()
