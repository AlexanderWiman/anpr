#!/usr/bin/env python3
"""Text-based installer fallback (no GUI)."""

from __future__ import annotations

import sys

from installer.engine import InstallConfig, check_prerequisites, run_install
from installer.sites import DEFAULT_BACKEND_URL, SITES


def main() -> None:
    print("=== ANPR Edge Agent — Installation ===\n")
    issues = check_prerequisites()
    for issue in issues:
        print(f"! {issue}")
    if issues:
        print()

    print("Anläggning:")
    for i, (_, label) in enumerate(SITES, 1):
        print(f"  {i}) {label}")
    choice = int(input("Val: ").strip() or "1")
    site_id = SITES[choice - 1][0]

    ip = input("Kamera-IP [192.168.0.96]: ").strip() or "192.168.0.96"
    print("Kameratyp: 1=Tapo  2=IP Webcam  3=Annan RTSP")
    cam_type = input("Typ [1]: ").strip() or "1"
    port = int(input("Port [554/8080]: ").strip() or ("8080" if cam_type == "2" else "554"))

    rtsp_path, rtsp_user, rtsp_pass = "/stream1", "", ""
    type_map = {"1": "tapo", "2": "ip_webcam", "3": "rtsp"}
    camera_type = type_map.get(cam_type, "tapo")
    if camera_type != "ip_webcam":
        rtsp_user = input("RTSP-användare: ").strip()
        rtsp_pass = input("RTSP-lösenord: ").strip()
    if camera_type == "rtsp":
        rtsp_path = input("RTSP-sökväg [/stream1]: ").strip() or "/stream1"

    token = input("Backend-token: ").strip()
    if not token:
        print("Token krävs.")
        sys.exit(1)

    cfg = InstallConfig(
        site_id=site_id,
        camera_ip=ip,
        camera_type=camera_type,
        camera_port=port,
        rtsp_path=rtsp_path,
        rtsp_user=rtsp_user,
        rtsp_password=rtsp_pass,
        camera_id="entrance-1",
        direction="entry",
        backend_url=DEFAULT_BACKEND_URL,
        anpr_token=token,
    )

    def log(msg: str) -> None:
        print(f"  {msg}")

    run_install(cfg, log)
    print("\nKlart! Öppna http://127.0.0.1:8080")


if __name__ == "__main__":
    main()
