from src.camera.base import FrameCaptureService
from src.camera.rtsp_capture import RTSPCaptureService
from src.config.settings import Settings


def create_capture_service(settings: Settings) -> FrameCaptureService:
    return RTSPCaptureService(settings)
