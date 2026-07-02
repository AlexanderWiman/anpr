"""Automatic retention for captured frames in storage/frames."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from src.utils.logging import get_logger

logger = get_logger(__name__)

FRAME_SUFFIXES = {".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class FrameCleanupResult:
    deleted_count: int
    freed_bytes: int
    remaining_count: int
    remaining_bytes: int


def _frame_files(frames_dir: Path) -> list[tuple[Path, float, int]]:
    """Return (path, mtime, size) for each frame file, oldest first."""
    if not frames_dir.is_dir():
        return []

    entries: list[tuple[Path, float, int]] = []
    for path in frames_dir.iterdir():
        if not path.is_file() or path.suffix.lower() not in FRAME_SUFFIXES:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        entries.append((path, stat.st_mtime, stat.st_size))

    entries.sort(key=lambda item: item[1])
    return entries


def cleanup_frames(
    frames_dir: Path,
    *,
    max_age_hours: float,
    max_files: int,
    max_storage_mb: int,
) -> FrameCleanupResult:
    """
    Enforce frame retention on disk.

    Limits use 0 as "disabled". When enabled, files are removed if they are
    older than max_age_hours, then oldest-first until count and total size
    are within max_files and max_storage_mb.
    """
    if max_age_hours <= 0 and max_files <= 0 and max_storage_mb <= 0:
        return FrameCleanupResult(0, 0, 0, 0)

    entries = _frame_files(frames_dir)
    if not entries:
        return FrameCleanupResult(0, 0, 0, 0)

    now = time.time()
    max_age_sec = max_age_hours * 3600 if max_age_hours > 0 else None
    max_bytes = max_storage_mb * 1024 * 1024 if max_storage_mb > 0 else None

    to_delete: list[Path] = []
    remaining: list[tuple[Path, float, int]] = []

    for path, mtime, size in entries:
        if max_age_sec is not None and (now - mtime) > max_age_sec:
            to_delete.append(path)
        else:
            remaining.append((path, mtime, size))

    def _mark_oldest(count: int) -> None:
        nonlocal remaining
        if count <= 0:
            return
        victims = remaining[:count]
        remaining = remaining[count:]
        to_delete.extend(path for path, _, _ in victims)

    if max_files > 0:
        overflow = len(remaining) - max_files
        if overflow > 0:
            _mark_oldest(overflow)

    if max_bytes is not None:
        total = sum(size for _, _, size in remaining)
        while remaining and total > max_bytes:
            path, _, size = remaining[0]
            remaining = remaining[1:]
            to_delete.append(path)
            total -= size

    deleted_count = 0
    freed_bytes = 0
    for path in to_delete:
        try:
            size = path.stat().st_size
            path.unlink()
            deleted_count += 1
            freed_bytes += size
        except OSError as exc:
            logger.warning(
                "frame delete failed",
                extra={"event": "frame_cleanup_error", "path": str(path), "error": str(exc)},
            )

    remaining_count = len(remaining)
    remaining_bytes = sum(size for _, _, size in remaining)

    return FrameCleanupResult(
        deleted_count=deleted_count,
        freed_bytes=freed_bytes,
        remaining_count=remaining_count,
        remaining_bytes=remaining_bytes,
    )
