# ANPR Edge Agent

> **Svenska — installation på anläggning:** [MANUAL_SV.md](MANUAL_SV.md)

Local service at the IP camera site: captures RTSP frames, reads license plates with YOLO+OCR, and POSTs events to the central backend.

## Quick start

```bash
./scripts/setup.sh
cp sites/falun.env.example sites/falun.env   # edit RTSP URL
# Edit .env.example values → merged on start (BACKEND_URL, ANPR_AGENT_TOKEN)
./scripts/start.sh
```

Open `http://127.0.0.1:8080` and click **Starta**.

## Site profiles

Shared settings live in `.env.example`. Per-site values in `sites/<name>.env`:

```env
SITE_ID=falun
CAMERA_ID=entrance-1
DIRECTION=entry
CAMERA_RTSP_URL=rtsp://user:pass@192.168.1.100:554/stream1
```

On start, `choose-site` merges `.env.example` + selected profile → `.env`.

**Windows:** double-click **Start ANPR** (see `scripts/install-worker-shortcut.ps1`).

**Fixed site (no menu):** set `ANPR_SITE_PROFILE=falun` before start.

## Windows service (production)

```powershell
.\scripts\setup.ps1
.\scripts\install-windows-service.ps1
.\scripts\install-worker-shortcut.ps1
```

## Linux systemd

```bash
sudo ./scripts/install-systemd.sh
```

## Docker

```bash
cp .env.example .env
cp sites/falun.env.example sites/falun.env
docker compose up --build
```

## Booking hints

When enabled (`BOOKING_HINTS_ENABLED=true`), the agent fetches today's expected plates from:

`GET /api/anpr/sites/{siteId}/expected-plates`

This helps disambiguate OCR errors (e.g. POE797 vs PUE797) without blocking drop-in vehicles.

## Architecture

```
IP Camera (RTSP) → YOLO + OCR → dedup → POST /api/anpr/events → Railway backend
```

## Requirements

- Python 3.11+
- FFmpeg (RTSP via OpenCV)
- Network to camera (LAN) and backend (HTTPS)
