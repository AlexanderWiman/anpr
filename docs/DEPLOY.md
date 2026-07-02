# Deployment — ANPR Edge Agent

Konfigurationsfiler för avancerad installation finns i mappen [`deploy/`](../deploy/).

## Site profiles

Per-location RTSP settings live in `sites/<name>.env` (copy from `sites/*.env.example`).
Shared backend/YOLO settings in `.env.example`.

Workers choose site at start via `choose-site` (Windows: `start-anpr.cmd`, Linux/Mac: `start.sh`).

## Windows

| File | Purpose |
|------|---------|
| `deploy/env.production.windows.example` | Legacy single-file env for NSSM install |
| `nssm.exe` | *(you provide)* — [download NSSM](https://nssm.cc/download) |

```powershell
.\scripts\setup.ps1
.\scripts\install-windows-service.ps1
.\scripts\install-worker-shortcut.ps1
```

## Linux

| File | Purpose |
|------|---------|
| `deploy/anpr-edge-agent.service` | systemd unit |
| `deploy/env.production.example` | Legacy single-file env for systemd |

```bash
sudo ./scripts/install-systemd.sh
```

## macOS

| File | Purpose |
|------|---------|
| `deploy/com.anpr.edge-agent.plist` | LaunchAgent template (user login) |

```bash
./scripts/install-mac.sh
./scripts/install-mac-shortcut.sh   # desktop only
./scripts/uninstall-mac.sh
```

## Docker

```bash
docker compose up --build
```

Requires `.env` in project root (copy from `.env.example`).
