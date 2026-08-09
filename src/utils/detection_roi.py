"""Helpers for optional detection region-of-interest (ROI)."""

from __future__ import annotations

import json
from typing import Any, Literal

RoiBand = Literal["top", "bottom"]


def clamp_roi_fraction(value: float) -> float:
    """Keep ROI fraction in (0, 1); invalid values disable cropping."""
    try:
        fraction = float(value)
    except (TypeError, ValueError):
        return 0.0
    if fraction <= 0 or fraction >= 1:
        return 0.0
    return fraction


# Backward-compatible alias used by older imports/tests.
clamp_roi_top_fraction = clamp_roi_fraction


def normalize_roi_band(value: Any) -> RoiBand:
    text = str(value or "top").strip().lower()
    return "bottom" if text == "bottom" else "top"


def detection_roi_slice(
    height: int,
    *,
    enabled: bool,
    fraction: float,
    band: RoiBand = "top",
    # Legacy kwarg name
    top_fraction: float | None = None,
) -> tuple[int, int]:
    """
    Return (y_start, y_end) for YOLO input cropping.

    band=top  → keep the upper `fraction` of the frame
    band=bottom → keep the lower `fraction` of the frame
    When disabled or invalid, returns the full frame (0, height).
    """
    if not enabled or height <= 0:
        return 0, height

    use_fraction = clamp_roi_fraction(
        top_fraction if top_fraction is not None else fraction
    )
    if use_fraction <= 0:
        return 0, height

    band = normalize_roi_band(band)
    if band == "bottom":
        y_start = min(height - 1, int(height * (1.0 - use_fraction)))
        return y_start, height

    y_end = max(1, int(height * use_fraction))
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
    fraction: float,
    had_detections: bool,
    band: RoiBand = "top",
    top_fraction: float | None = None,
) -> bool:
    """
    True when ROI was active but found nothing — retry full frame.

    Covers plates outside the configured band (parked close / far end).
    """
    if had_detections or not roi_enabled or frame_height <= 0:
        return False
    y_start, y_end = detection_roi_slice(
        frame_height,
        enabled=True,
        fraction=top_fraction if top_fraction is not None else fraction,
        band=band,
    )
    return not (y_start == 0 and y_end == frame_height)


def parse_detection_roi_by_camera(raw: str | dict | None) -> dict[str, dict[str, Any]]:
    """
    Parse DETECTION_ROI_BY_CAMERA JSON.

    Example:
      {"entrance-1":{"band":"top","fraction":0.45},"entrance-2":{"band":"bottom","fraction":0.40}}
    """
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        data = raw
    else:
        try:
            data = json.loads(str(raw))
        except (TypeError, json.JSONDecodeError):
            return {}
    if not isinstance(data, dict):
        return {}

    parsed: dict[str, dict[str, Any]] = {}
    for camera_id, cfg in data.items():
        key = str(camera_id).strip()
        if not key or not isinstance(cfg, dict):
            continue
        enabled = cfg.get("enabled", True)
        if isinstance(enabled, str):
            enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
        fraction = clamp_roi_fraction(cfg.get("fraction", cfg.get("top_fraction", 0.35)))
        if not enabled or fraction <= 0:
            parsed[key] = {"enabled": False, "band": "top", "fraction": 0.0}
            continue
        parsed[key] = {
            "enabled": True,
            "band": normalize_roi_band(cfg.get("band", "top")),
            "fraction": fraction,
        }
    return parsed


def merge_camera_config_roi_overrides(
    by_camera: dict[str, dict[str, Any]] | None,
    cameras: list[Any] | None,
) -> dict[str, dict[str, Any]]:
    """
    Merge ROI from CameraConfig (e.g. CRM remote config) over env map.

    Camera fields win when detection_roi_enabled is not None.
    """
    merged = dict(by_camera or {})
    for camera in cameras or []:
        enabled = getattr(camera, "detection_roi_enabled", None)
        if enabled is None:
            continue
        camera_id = str(getattr(camera, "id", "") or "").strip()
        if not camera_id:
            continue
        if not enabled:
            merged[camera_id] = {"enabled": False, "band": "top", "fraction": 0.0}
            continue
        fraction = clamp_roi_fraction(
            getattr(camera, "detection_roi_fraction", None) or 0.0
        )
        if fraction <= 0:
            merged[camera_id] = {"enabled": False, "band": "top", "fraction": 0.0}
            continue
        merged[camera_id] = {
            "enabled": True,
            "band": normalize_roi_band(
                getattr(camera, "detection_roi_band", None) or "top"
            ),
            "fraction": fraction,
        }
    return merged


def resolve_camera_roi(
    camera_id: str | None,
    *,
    site_enabled: bool,
    site_top_fraction: float,
    by_camera: dict[str, dict[str, Any]] | None,
) -> tuple[bool, RoiBand, float]:
    """
    Resolve ROI for one camera.

    Per-camera map wins when present; otherwise fall back to site-wide top ROI.
    """
    overrides = by_camera or {}
    key = (camera_id or "").strip()
    if key and key in overrides:
        cfg = overrides[key]
        return (
            bool(cfg.get("enabled")),
            normalize_roi_band(cfg.get("band", "top")),
            float(cfg.get("fraction") or 0.0),
        )
    if not site_enabled:
        return False, "top", 0.0
    fraction = clamp_roi_fraction(site_top_fraction)
    if fraction <= 0:
        return False, "top", 0.0
    return True, "top", fraction
