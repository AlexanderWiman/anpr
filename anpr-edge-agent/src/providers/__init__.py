"""Plate recognition providers."""

from src.providers.base import PlateProvider
from src.providers.factory import create_plate_provider
from src.providers.yolo_ocr_provider import YoloOcrPlateProvider

__all__ = ["PlateProvider", "YoloOcrPlateProvider", "create_plate_provider"]
