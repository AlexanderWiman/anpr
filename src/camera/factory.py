from src.camera.base import FrameCaptureService
from src.camera.rtsp_capture import RTSPCaptureService
from src.config.cameras import CameraConfig
from src.config.settings import Settings


def create_capture_service(
    settings: Settings,
    camera: CameraConfig | None = None,
) -> FrameCaptureService:
    return RTSPCaptureService(settings, camera or settings.primary_camera)
