"""User-facing Swedish status text for RTSP camera errors."""

from __future__ import annotations


def rtsp_host_label(rtsp_url: str) -> str:
    """Return host:port from an RTSP URL for display (no credentials)."""
    url = (rtsp_url or "").strip()
    if not url:
        return "kameran"
    if "@" in url:
        host_part = url.rsplit("@", 1)[-1]
    elif "://" in url:
        host_part = url.split("://", 1)[1]
    else:
        host_part = url
    return host_part.split("/", 1)[0] or "kameran"


def camera_status_message(
    *,
    status: str,
    reason: str | None = None,
    rtsp_url: str = "",
    timeout_ms: int | None = None,
) -> str | None:
    """Map internal camera state to a short Swedish hint for dashboard/CRM."""
    host = rtsp_host_label(rtsp_url)
    timeout_sec = round((timeout_ms or 10_000) / 1000)

    if status == "connecting":
        return f"Ansluter till {host}…"

    if status == "reconnecting":
        if reason == "read_timeout":
            return f"Strömmen till {host} avbröts (timeout). Försöker igen…"
        if reason == "empty_frame":
            return f"Tom bild från {host}. Försöker igen…"
        return f"Tappade anslutningen till {host}. Försöker igen…"

    if status == "error":
        if reason == "connection_timeout":
            return (
                f"Timeout mot {host} ({timeout_sec} s). "
                "Pinga IP från verkstadsdatorn och kontrollera att kameran är på samma nät."
            )
        if reason == "stream_not_opened":
            return (
                f"Kan inte öppna RTSP mot {host}. "
                "Kontrollera IP, Tapo Camera Account och att integritetsläge är av."
            )
        if reason == "no_frame_received":
            return (
                f"Ingen bild från {host}. "
                "Ofta fel RTSP-lösenord — testa samma URL i VLC."
            )
        if reason == "read_timeout":
            return f"Strömmen till {host} svarar inte (timeout)."
        if reason == "empty_frame":
            return f"Tom bild från {host}."
        return f"Kamerafel mot {host}."

    if status == "disconnected":
        return "Kameran är frånkopplad."

    return None
