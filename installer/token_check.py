"""Validate backend token during installation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


def validate_backend_credentials(
    *,
    site_id: str,
    backend_url: str,
    token: str,
    timeout_seconds: float = 15.0,
) -> tuple[bool, str]:
    """Return (ok, message) after calling the authenticated backend API."""
    base = backend_url.rstrip("/")
    url = f"{base}/api/anpr/sites/{site_id.strip()}/expected-plates"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token.strip()}",
            "Accept": "application/json",
            "User-Agent": "anpr-edge-agent-installer/1.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            if 200 <= response.status < 300:
                return True, "Token godkänd av backend"
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except OSError:
            pass
        if exc.code in (401, 403):
            return False, "Token ogiltig — kontrollera med IT och försök igen"
        if exc.code == 422:
            try:
                payload = json.loads(body)
                message = payload.get("message")
                if isinstance(message, str) and message:
                    return False, message
            except json.JSONDecodeError:
                pass
            return False, "Okänd anläggning — kontrollera SITE_ID"
        if exc.code == 404:
            return False, "Backend saknar ANPR-endpoint — kontakta IT"
        return False, f"Backend svarade med fel {exc.code}"
    except urllib.error.URLError as exc:
        return False, f"Kan inte nå backend: {exc.reason}"

    return False, "Kunde inte verifiera token mot backend"
