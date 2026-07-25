"""Persist the latest JPEG preview per camera for the web dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

    from src.config.settings import Settings


def preview_path(settings: "Settings", camera_id: str) -> Path:
    directory = settings.storage_dir / "previews"
    directory.mkdir(parents=True, exist_ok=True)
    safe_id = camera_id.replace("/", "_").replace("\\", "_") or "camera"
    return directory / f"{safe_id}.jpg"


def write_camera_preview(
    settings: "Settings",
    camera_id: str,
    frame: "np.ndarray",
    *,
    max_width: int = 960,
    quality: int = 75,
) -> Path | None:
    import cv2

    if frame is None or frame.size == 0:
        return None

    image = frame
    height, width = image.shape[:2]
    if width > max_width:
        scale = max_width / width
        image = cv2.resize(
            image,
            (max_width, max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )

    path = preview_path(settings, camera_id)
    ok = cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return path if ok else None
