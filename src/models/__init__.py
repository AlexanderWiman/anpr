"""Data models."""

from src.models.detection import BoundingBox, PlateDetection
from src.models.event import AnprEvent, QueuedEvent

__all__ = ["BoundingBox", "PlateDetection", "AnprEvent", "QueuedEvent"]
