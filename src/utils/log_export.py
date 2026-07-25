"""Collect and compress agent logs for remote export."""

from __future__ import annotations

import base64
import gzip
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.utils.log_reader import _ALLOWED_NAMES, resolve_log_dir

_LOG_TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H:%M:%S,%f",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)

_DEFAULT_MAX_GZIP_BYTES = 1_800_000


@dataclass(frozen=True)
class LogExportBundle:
    hours: float
    exported_at: str
    line_count: int
    truncated: bool
    original_bytes: int
    compressed_bytes: int
    content_gzip_base64: str

    def as_upload_payload(self, request_id: str, *, status: str = "completed") -> dict:
        payload = {
            "requestId": request_id,
            "status": status,
            "hours": self.hours,
            "lineCount": self.line_count,
            "exportedAt": self.exported_at,
            "truncated": self.truncated,
            "originalBytes": self.original_bytes,
            "compressedBytes": self.compressed_bytes,
        }
        if status == "completed":
            payload["contentGzipBase64"] = self.content_gzip_base64
        return payload


def _parse_log_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    for fmt in _LOG_TIMESTAMP_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _iter_log_files(log_dir: Path) -> list[Path]:
    root = resolve_log_dir(log_dir)
    files: list[Path] = []
    for name in sorted(_ALLOWED_NAMES):
        path = root / name
        if path.is_file():
            files.append(path)
    agent_log = root / "agent.log"
    if agent_log.is_file():
        for rotated in sorted(root.glob("agent.log.*")):
            if rotated.is_file() and rotated not in files:
                files.append(rotated)
    return files


def collect_log_lines_since(
    log_dir: Path,
    *,
    hours: float = 24.0,
    now: datetime | None = None,
) -> tuple[list[str], dict]:
    """Return raw log lines from the last ``hours`` hours, oldest first."""
    root = resolve_log_dir(log_dir)
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=max(0.1, hours))
    matched: list[tuple[datetime | None, str]] = []
    scanned = 0

    for path in _iter_log_files(root):
        if path.name not in _ALLOWED_NAMES and not path.name.startswith("agent.log"):
            continue
        include_undated = path.name == "agent-startup.log"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            scanned += 1
            raw = line.strip()
            if not raw:
                continue
            timestamp = None
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    timestamp = _parse_log_timestamp(str(payload.get("timestamp") or ""))
            except json.JSONDecodeError:
                pass
            if timestamp is not None and timestamp < cutoff:
                continue
            if timestamp is None and not include_undated:
                continue
            matched.append((timestamp, raw))

    matched.sort(key=lambda item: (item[0] is None, item[0] or datetime.min.replace(tzinfo=timezone.utc)))
    lines = [line for _, line in matched]
    return lines, {
        "logDir": str(root),
        "hours": hours,
        "cutoff": cutoff.isoformat(),
        "scanned": scanned,
        "matched": len(lines),
        "files": [str(path) for path in _iter_log_files(root)],
    }


def build_log_export(
    log_dir: Path,
    *,
    hours: float = 24.0,
    max_gzip_bytes: int = _DEFAULT_MAX_GZIP_BYTES,
    now: datetime | None = None,
) -> LogExportBundle:
    """Build a gzip-compressed log bundle for upload."""
    lines, _meta = collect_log_lines_since(log_dir, hours=hours, now=now)
    truncated = False
    text = "\n".join(lines)
    if lines:
        text += "\n"

    while True:
        compressed = gzip.compress(text.encode("utf-8"))
        if len(compressed) <= max_gzip_bytes or not lines:
            break
        truncated = True
        drop = max(1, len(lines) // 10)
        lines = lines[drop:]
        text = "\n".join(lines)
        if lines:
            text += "\n"

    exported_at = (now or datetime.now(timezone.utc)).isoformat()
    original_bytes = len(text.encode("utf-8"))
    return LogExportBundle(
        hours=hours,
        exported_at=exported_at,
        line_count=len(lines),
        truncated=truncated,
        original_bytes=original_bytes,
        compressed_bytes=len(compressed),
        content_gzip_base64=base64.b64encode(compressed).decode("ascii"),
    )
