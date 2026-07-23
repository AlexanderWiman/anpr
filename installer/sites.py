"""Site list for the installer wizard."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class SiteProfile:
    id: str
    label: str
    default_halls: int = 1
    max_halls: int = 2


SITE_PROFILES: list[SiteProfile] = [
    SiteProfile("falun", "Falun", default_halls=2, max_halls=2),
    SiteProfile("borlange", "Borlänge"),
    SiteProfile("gavle", "Gävle"),
    SiteProfile("rattvik", "Rättvik"),
    SiteProfile("leksand", "Leksand"),
    SiteProfile("lulea", "Luleå"),
    SiteProfile("umea", "Umeå"),
    SiteProfile("stockholm", "Stockholm"),
]

# Backward-compatible tuples for CLI
SITES: list[tuple[str, str]] = [(site.id, site.label) for site in SITE_PROFILES]

DEFAULT_BACKEND_URL = "https://backend-production-c702.up.railway.app"


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_installer_sites(backend_url: str | None = None) -> tuple[list[SiteProfile], str]:
    """Load active locations from backend; fall back to local SITE_PROFILES."""
    base = (backend_url or DEFAULT_BACKEND_URL).rstrip("/")
    url = f"{base}/api/anpr/installer/sites"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "anpr-edge-agent-installer/1.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=15.0,
            context=_ssl_context(),
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        items = payload.get("sites") or []
        profiles: list[SiteProfile] = []
        for item in items:
            site_id = str(item.get("id") or "").strip()
            label = str(item.get("label") or "").strip()
            if not site_id or not label:
                continue
            profiles.append(
                SiteProfile(
                    id=site_id,
                    label=label,
                    default_halls=max(1, min(int(item.get("defaultHalls") or 1), 2)),
                    max_halls=max(1, min(int(item.get("maxHalls") or 2), 2)),
                )
            )
        if profiles:
            return profiles, base
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        ValueError,
    ):
        pass

    return SITE_PROFILES, base


def site_profile(site_id: str) -> SiteProfile | None:
    for site in SITE_PROFILES:
        if site.id == site_id:
            return site
    return None
