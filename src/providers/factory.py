from src.config.settings import Settings
from src.providers.base import PlateProvider
from src.providers.yolo_ocr_provider import YoloOcrPlateProvider
from src.services.booking_hints import BookingHintService


def create_plate_provider(
    settings: Settings,
    booking_hints: BookingHintService | None = None,
) -> PlateProvider:
    return YoloOcrPlateProvider(settings, booking_hints=booking_hints)
