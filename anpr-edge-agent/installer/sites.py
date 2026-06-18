"""Site list for the installer wizard."""

SITES: list[tuple[str, str]] = [
    ("falun", "Falun"),
    ("borlange", "Borlänge"),
    ("gavle", "Gävle"),
    ("rattvik", "Rättvik"),
    ("leksand", "Leksand"),
    ("lulea", "Luleå"),
    ("umea", "Umeå"),
]

DEFAULT_BACKEND_URL = "https://backend-production-c702.up.railway.app"
