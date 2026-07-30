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


def roi_upscale_factor(width: int, *, target_width: int) -> float:
    """Scale ROI so distant plates occupy more pixels for YOLO."""
    if width <= 0 or target_width <= 0 or width >= target_width:
        return 1.0
    return target_width / width


def map_box_from_roi(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    *,
    y_offset: int,
    scale: float,
) -> tuple[int, int, int, int]:
    """Map YOLO box coords from (possibly upscaled) ROI back to full-frame pixels."""
    if scale <= 0:
        scale = 1.0
    return (
        int(round(x1 / scale)),
        int(round(y1 / scale)) + y_offset,
        int(round(x2 / scale)),
        int(round(y2 / scale)) + y_offset,
    )


def should_full_frame_fallback(
    *,
    roi_enabled: bool,
    frame_height: int,
    top_fraction: float,
    had_detections: bool,
) -> bool:
    """
    True when top-ROI was active but found nothing — retry full frame.

    Covers parked cars whose plates sit near the bottom edge (outside top ROI).
    Periodic stills use the same detector path, so they need this too.
    """
    if had_detections or not roi_enabled or frame_height <= 0:
        return False
    _, y_end = detection_roi_slice(
        frame_height, enabled=True, top_fraction=top_fraction
    )
    return 0 < y_end < frame_height
