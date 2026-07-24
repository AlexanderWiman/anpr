"""Read recent agent log lines for the local dashboard."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "WARN": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

_ALLOWED_NAMES = frozenset({"agent.log", "agent-startup.log"})


@dataclass(frozen=True)
class LogEntry:
    timestamp: str | None
    level: str
    logger: str | None
    message: str
    event: str | None
    source: str
    raw: str

    def as_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
            "event": self.event,
            "source": self.source,
            "raw": self.raw,
        }


def _min_level_value(level: str | None) -> int | None:
    if not level:
        return None
    normalized = level.strip().upper()
    if normalized in ("WARNING", "WARN"):
        return _LOG_LEVELS["WARNING"]
    if normalized == "ERROR":
        return _LOG_LEVELS["ERROR"]
    if normalized == "INFO":
        return _LOG_LEVELS["INFO"]
    return None


def _parse_log_line(line: str, *, source: str) -> LogEntry | None:
    text = line.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return LogEntry(
            timestamp=None,
            level="INFO",
            logger=None,
            message=text,
            event=None,
            source=source,
            raw=text,
        )
    if not isinstance(payload, dict):
        return LogEntry(
            timestamp=None,
            level="INFO",
            logger=None,
            message=text,
            event=None,
            source=source,
            raw=text,
        )
    level = str(payload.get("level") or "INFO").upper()
    return LogEntry(
        timestamp=payload.get("timestamp"),
        level=level,
        logger=payload.get("logger"),
        message=str(payload.get("message") or text),
        event=payload.get("event"),
        source=source,
        raw=text,
    )


def _tail_text(path: Path, *, max_bytes: int = 512_000) -> str:
    if not path.is_file():
        return ""
    size = path.stat().st_size
    if size <= max_bytes:
        return path.read_text(encoding="utf-8", errors="replace")
    with path.open("rb") as handle:
        handle.seek(max(0, size - max_bytes))
        chunk = handle.read()
    text = chunk.decode("utf-8", errors="replace")
    if "\n" in text:
        text = text.split("\n", 1)[1]
    return text


def _tail_lines(path: Path, limit: int) -> list[str]:
    text = _tail_text(path)
    if not text:
        return []
    lines = text.splitlines()
    if len(lines) <= limit:
        return lines
    return lines[-limit:]


def log_file_info(path: Path) -> dict | None:
    if not path.is_file():
        return None
    stat = path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    return {
        "name": path.name,
        "path": str(path),
        "size": stat.st_size,
        "modifiedAt": modified,
    }


def resolve_log_dir(log_dir: Path) -> Path:
    return log_dir.expanduser().resolve()


def list_log_files(log_dir: Path) -> list[dict]:
    root = resolve_log_dir(log_dir)
    files: list[dict] = []
    for name in ("agent.log", "agent-startup.log"):
        info = log_file_info(root / name)
        if info:
            files.append(info)
    return files


def read_recent_logs(
    log_dir: Path,
    *,
    tail: int = 200,
    min_level: str | None = None,
    source: str = "agent",
    query: str | None = None,
    scan_lines: int | None = None,
) -> dict:
    root = resolve_log_dir(log_dir)
    tail = max(1, min(tail, 1000))
    min_value = _min_level_value(min_level)
    search = query.strip().lower() if query else ""

    if search:
        per_file = min(max(scan_lines or 5000, tail * 20), 20_000)
    elif source == "all":
        per_file = max(tail, 50)
    else:
        per_file = tail

    sources: list[tuple[str, Path]] = []
    if source in ("agent", "all"):
        sources.append(("agent.log", root / "agent.log"))
    if source in ("startup", "all"):
        sources.append(("agent-startup.log", root / "agent-startup.log"))

    entries: list[LogEntry] = []
    scanned = 0
    for name, path in sources:
        if path.name not in _ALLOWED_NAMES:
            continue
        if not str(path.resolve()).startswith(str(root)):
            continue
        lines = _tail_lines(path, per_file)
        scanned += len(lines)
        for line in lines:
            entry = _parse_log_line(line, source=name)
            if entry is None:
                continue
            if min_value is not None:
                if _LOG_LEVELS.get(entry.level, 0) < min_value:
                    continue
            if search and not _entry_matches_query(entry, search):
                continue
            entries.append(entry)

    entries.sort(key=lambda item: item.timestamp or "")
    matched = len(entries)
    if len(entries) > tail:
        entries = entries[-tail:]

    return {
        "logDir": str(root),
        "files": list_log_files(log_dir),
        "entries": [entry.as_dict() for entry in entries],
        "tail": tail,
        "level": min_level,
        "source": source,
        "query": query or "",
        "matched": matched,
        "scanned": scanned,
    }


def _entry_matches_query(entry: LogEntry, query: str) -> bool:
    haystacks = (
        entry.message,
        entry.event,
        entry.logger,
        entry.raw,
        entry.source,
    )
    return any(query in str(value).lower() for value in haystacks if value)
