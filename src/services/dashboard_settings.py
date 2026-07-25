"""Read-only dashboard view of agent environment variables."""

from __future__ import annotations

import re
from pathlib import Path

from src.config.settings import settings_env_path

_SENSITIVE_PATTERN = re.compile(
    r"(TOKEN|PASSWORD|SECRET|API_KEY|PRIVATE)",
    re.IGNORECASE,
)


def _mask_value(key: str, value: str) -> str:
    if not value:
        return value
    if _SENSITIVE_PATTERN.search(key):
        if len(value) <= 4:
            return "****"
        return f"{value[:2]}…{value[-2:]}"
    if key.upper().endswith("_URL") and "@" in value:
        scheme, rest = value.split("://", 1)
        if "@" in rest:
            _, host = rest.rsplit("@", 1)
            return f"{scheme}://***@{host}"
    return value


def _parse_env_lines(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def build_dashboard_settings_payload() -> dict:
    path_str = settings_env_path()
    if not path_str:
        return {"configPath": None, "settings": {}}

    path = Path(path_str)
    if not path.is_file():
        return {"configPath": str(path), "settings": {}}

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {"configPath": str(path), "settings": {}}

    parsed = _parse_env_lines(raw)
    settings = {key: _mask_value(key, value) for key, value in sorted(parsed.items())}
    return {"configPath": str(path), "settings": settings}
