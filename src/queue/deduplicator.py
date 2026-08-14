from datetime import datetime, timezone

from src.config.settings import Settings
from src.utils.logging import get_logger
from src.utils.plates import (
    is_likely_suffix_misread,
    normalize_plate,
    plate_suffix,
)

logger = get_logger(__name__)


class PlateDeduplicator:
    """
    Suppress duplicate plate detections within a cooldown window.

    Tracks last seen time per normalized plate and rejects likely OCR misreads
    that share a numeric suffix with a previously confirmed plate (POE797 vs PUE797).
    """

    def __init__(self, settings: Settings) -> None:
        self._cooldown_seconds = settings.plate_cooldown_seconds
        self._last_seen: dict[str, datetime] = {}
        self._suffix_best: dict[str, tuple[str, float]] = {}
        self._plate_confidence: dict[str, float] = {}

    @property
    def cooldown_seconds(self) -> int:
        return self._cooldown_seconds

    def should_accept(self, plate: str, confidence: float = 1.0) -> bool:
        normalized = normalize_plate(plate)
        now = datetime.now(timezone.utc)

        suffix = plate_suffix(normalized)
        if suffix is not None:
            known = self._suffix_best.get(suffix)
            if known is not None:
                known_plate, known_conf = known
                if is_likely_suffix_misread(
                    normalized, known_plate, known_conf, confidence
                ):
                    logger.info(
                        "misread rejected",
                        extra={
                            "event": "misread_rejected",
                            "plate": normalized,
                            "confidence": confidence,
                            "reference_plate": known_plate,
                            "reference_confidence": known_conf,
                            "suffix": suffix,
                        },
                    )
                    return False

        # Near OCR variants of a recently accepted plate (covers ABC12A / 0↔D).
        for seen_plate, seen_at in self._last_seen.items():
            if seen_plate == normalized:
                continue
            if (now - seen_at).total_seconds() > self._cooldown_seconds:
                continue
            prev_conf = self._plate_confidence.get(seen_plate, 1.0)
            if is_likely_suffix_misread(normalized, seen_plate, prev_conf, confidence):
                logger.info(
                    "misread rejected",
                    extra={
                        "event": "misread_rejected",
                        "plate": normalized,
                        "confidence": confidence,
                        "reference_plate": seen_plate,
                        "reference_confidence": prev_conf,
                    },
                )
                return False

        last = self._last_seen.get(normalized)
        if last is not None:
            elapsed = (now - last).total_seconds()
            if elapsed < self._cooldown_seconds:
                logger.info(
                    "duplicate ignored",
                    extra={
                        "event": "duplicate_ignored",
                        "plate": normalized,
                        "seconds_since_last": round(elapsed, 1),
                        "cooldown_seconds": self._cooldown_seconds,
                    },
                )
                return False

        return True

    def mark_submitted(self, plate: str, confidence: float = 1.0) -> None:
        """Record that an event was queued or delivered for this plate."""
        normalized = normalize_plate(plate)
        now = datetime.now(timezone.utc)
        self._last_seen[normalized] = now
        self._plate_confidence[normalized] = confidence
        suffix = plate_suffix(normalized)
        if suffix is not None:
            prev = self._suffix_best.get(suffix)
            if prev is None or confidence >= prev[1]:
                self._suffix_best[suffix] = (normalized, confidence)

    def reset(self) -> None:
        self._last_seen.clear()
        self._suffix_best.clear()
        self._plate_confidence.clear()

    @property
    def last_detection(self) -> dict | None:
        if not self._last_seen:
            return None
        plate, ts = max(self._last_seen.items(), key=lambda x: x[1])
        return {
            "plate": plate,
            "seen_at": ts.isoformat(),
        }
