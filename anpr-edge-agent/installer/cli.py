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
    cam_type = input("Typ: 1=IP Webcam 2=RTSP [1]: ").strip() or "1"
    port = int(input("Port [8080/554]: ").strip() or ("554" if cam_type == "2" else "8080"))

    rtsp_path, rtsp_user, rtsp_pass = "/stream1", "", ""
    if cam_type == "2":
        rtsp_path = input("RTSP-sökväg [/stream1]: ").strip() or "/stream1"
        rtsp_user = input("RTSP-användare (tom om ingen): ").strip()
        rtsp_pass = input("RTSP-lösenord: ").strip()

    token = input("Backend-token: ").strip()
    if not token:
        print("Token krävs.")
        sys.exit(1)

    cfg = InstallConfig(
        site_id=site_id,
        camera_ip=ip,
        camera_type="rtsp" if cam_type == "2" else "ip_webcam",
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
