"""Capture a single diagnostic JPEG frame from the RTSP stream."""

from __future__ import annotations

import base64
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config.settings import Settings


def capture_rtsp_jpeg_base64(
    settings: "Settings",
    *,
    max_width: int = 1280,
    quality: int = 80,
) -> tuple[str, int, int]:
    import cv2

    url = settings.camera_rtsp_url
    transport = (settings.rtsp_transport or "tcp").strip().lower()
    if transport in ("tcp", "udp"):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{transport}"

    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    try:
        if not cap.isOpened():
            raise RuntimeError("Kunde inte öppna RTSP-strömmen")

        ret, frame = cap.read()
        if not ret or frame is None:
            raise RuntimeError("Ingen bild mottagen från kameran")

        height, width = frame.shape[:2]
        if width > max_width:
            scale = max_width / width
            frame = cv2.resize(
                frame,
                (max_width, max(1, int(height * scale))),
                interpolation=cv2.INTER_AREA,
            )

        height, width = frame.shape[:2]
        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("Kunde inte koda JPEG")

        encoded = base64.b64encode(buffer.tobytes()).decode("ascii")
        return encoded, width, height
    finally:
        cap.release()
