"""Build RTSP/HTTP capture URLs from structured camera fields."""

from __future__ import annotations

from urllib.parse import quote


def build_rtsp_url(
    *,
    camera_type: str,
    camera_ip: str,
    camera_port: int,
    rtsp_path: str = "/stream1",
    rtsp_user: str | None = None,
    rtsp_password: str | None = None,
) -> str:
    ip = camera_ip.strip()
    if camera_type == "ip_webcam":
        port = camera_port or 8080
        return f"http://{ip}:{port}/videofeed"

    port = camera_port or 554
    if camera_type == "tapo":
        path = "/stream1"
    else:
        path = (rtsp_path or "/stream1").strip()
    if not path.startswith("/"):
        path = f"/{path}"

    if rtsp_user:
        user = quote(rtsp_user, safe="")
        password = quote(rtsp_password or "", safe="")
        auth = f"{user}:{password}@" if rtsp_password else f"{user}@"
        return f"rtsp://{auth}{ip}:{port}{path}"
    return f"rtsp://{ip}:{port}{path}"
