"""Helpers for optional detection region-of-interest (ROI)."""

from __future__ import annotations


def clamp_roi_top_fraction(value: float) -> float:
    """Keep ROI fraction in (0, 1); invalid values disable cropping."""
    try:
        fraction = float(value)
    except (TypeError, ValueError):
        return 0.0
    if fraction <= 0 or fraction >= 1:
        return 0.0
    return fraction


def detection_roi_slice(
    height: int,
    *,
    enabled: bool,
    top_fraction: float,
) -> tuple[int, int]:
    """
    Return (y_start, y_end) for YOLO input cropping.

    When disabled or invalid, returns the full frame (0, height).
    """
    if not enabled or height <= 0:
        return 0, height

    fraction = clamp_roi_top_fraction(top_fraction)
    if fraction <= 0:
        return 0, height

    y_end = max(1, int(height * fraction))
    if y_end >= height:
        return 0, height
    return 0, y_end
