"""Lightweight motion gate — skip expensive OCR when the scene is static."""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

from src.utils.logging import get_logger

logger = get_logger(__name__)


class MotionGate:
    """
    Detect scene changes between frames.

    When idle, only a cheap pixel-diff check runs. After motion is seen,
    OCR stays enabled for ``active_seconds`` so a passing vehicle is
    captured across multiple frames.
    """

    def __init__(
        self,
        *,
        threshold: float,
        active_seconds: float,
        downscale_width: int = 320,
    ) -> None:
        self._threshold = threshold
        self._active_seconds = active_seconds
        self._downscale_width = downscale_width
        self._reference: np.ndarray | None = None
        self._active_until = 0.0
        self._frames_skipped = 0
        self._activations = 0

    @property
    def is_active(self) -> bool:
        return time.monotonic() < self._active_until

    @property
    def stats(self) -> dict:
        return {
            "active": self.is_active,
            "activations": self._activations,
            "frames_skipped": self._frames_skipped,
        }

    def reset(self) -> None:
        """Clear reference frame — next capture establishes a new baseline."""
        self._reference = None
        self._active_until = 0.0

    def activate(self, seconds: float | None = None) -> None:
        """Force OCR for a period (e.g. after Start when a car is already in frame)."""
        duration = self._active_seconds if seconds is None else seconds
        self._active_until = time.monotonic() + duration
        self._activations += 1
        logger.info(
            "motion gate activated manually",
            extra={
                "event": "motion_active",
                "score": None,
                "active_seconds": duration,
                "reason": "agent_start",
            },
        )

    def should_process(self, frame_path: Path) -> bool:
        """Return True when the frame should be sent to OCR."""
        image = cv2.imread(str(frame_path))
        if image is None:
            return True

        gray = self._downscale_gray(image)
        now = time.monotonic()

        if now < self._active_until:
            self._reference = gray
            return True

        if self._reference is None:
            self._reference = gray
            self._frames_skipped += 1
            return False

        score = self._diff_score(self._reference, gray)
        self._reference = gray

        if score >= self._threshold:
            self._active_until = now + self._active_seconds
            self._activations += 1
            logger.info(
                "motion detected — OCR active",
                extra={
                    "event": "motion_active",
                    "score": round(score, 4),
                    "active_seconds": self._active_seconds,
                },
            )
            return True

        self._frames_skipped += 1
        logger.debug(
            "no motion — skipping OCR",
            extra={"event": "motion_skipped", "score": round(score, 4)},
        )
        return False

    def _downscale_gray(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        width = self._downscale_width
        if w > width:
            scale = width / w
            image = cv2.resize(
                image,
                (width, max(1, int(h * scale))),
                interpolation=cv2.INTER_AREA,
            )
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _diff_score(previous: np.ndarray, current: np.ndarray) -> float:
        if previous.shape != current.shape:
            current = cv2.resize(
                current,
                (previous.shape[1], previous.shape[0]),
                interpolation=cv2.INTER_AREA,
            )
        diff = cv2.absdiff(previous, current)
        return float(diff.mean()) / 255.0
