"""Site list for the installer wizard."""

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
]

# Backward-compatible tuples for CLI
SITES: list[tuple[str, str]] = [(site.id, site.label) for site in SITE_PROFILES]

DEFAULT_BACKEND_URL = "https://backend-production-c702.up.railway.app"


def site_profile(site_id: str) -> SiteProfile | None:
    for site in SITE_PROFILES:
        if site.id == site_id:
            return site
    return None
