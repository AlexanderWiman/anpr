"""Require the same plate on multiple consecutive frames before delivery."""

from collections import Counter

from src.utils.plates import normalize_plate


class FramePlateBuffer:
    """
    Buffers recent frame reads and confirms a plate only when it appears
    at least twice in the last N frames.

    After a plate is confirmed once, it is ignored until an empty frame clears
    the scene — prevents re-firing on long clips where the same car stays visible.
    """

    def __init__(self, window_size: int = 3, min_hits: int = 2) -> None:
        self._window_size = window_size
        self._min_hits = min_hits
        self._recent: list[tuple[str, float]] = []
        self._handled_plate: str | None = None

    def observe(self, plate: str, confidence: float) -> tuple[str, float] | None:
        """
        Record a detection. Returns (plate, avg_confidence) when confirmed, else None.
        """
        normalized = normalize_plate(plate)
        if self._handled_plate == normalized:
            return None

        self._recent.append((normalized, confidence))
        if len(self._recent) > self._window_size:
            self._recent.pop(0)

        if len(self._recent) < self._min_hits:
            return None

        counts = Counter(p for p, _ in self._recent)
        best_plate, hits = counts.most_common(1)[0]
        if hits < self._min_hits:
            return None

        if normalized != best_plate:
            return None

        confidences = [c for p, c in self._recent if p == best_plate]
        return best_plate, sum(confidences) / len(confidences)

    def mark_handled(self, plate: str) -> None:
        """Stop re-confirming this plate until the scene is empty."""
        self._handled_plate = normalize_plate(plate)
        self._recent.clear()

    def observe_empty(self) -> None:
        """Scene has no plate — allow the next vehicle to be confirmed."""
        self._handled_plate = None
        self._recent.clear()

    def clear(self) -> None:
        self._handled_plate = None
        self._recent.clear()
