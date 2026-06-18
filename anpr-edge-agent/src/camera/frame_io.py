"""Lossless frame persistence for OCR — JPEG compression breaks plate contour detection."""

from datetime import datetime
from uuid import uuid4

import cv2
import numpy as np


def frame_filename(prefix: str = "frame") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{prefix}_{ts}_{uuid4().hex[:8]}.png"


def save_frame(path: str | bytes, image: np.ndarray) -> bool:
    """Save a captured frame as PNG (lossless) for reliable OCR preprocessing."""
    return bool(cv2.imwrite(str(path), image))
