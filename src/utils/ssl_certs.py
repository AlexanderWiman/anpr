"""Ensure HTTPS downloads use certifi's CA bundle (common Windows fix)."""

from __future__ import annotations

import os


def configure_ssl_certificates() -> str | None:
    try:
        import certifi
    except ImportError:
        return None

    bundle = certifi.where()
    if not bundle:
        return None

    os.environ.setdefault("SSL_CERT_FILE", bundle)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle)
    return bundle
