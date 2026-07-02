"""Event queue and deduplication."""

from src.queue.deduplicator import PlateDeduplicator
from src.queue.event_queue import EventQueue

__all__ = ["PlateDeduplicator", "EventQueue"]
