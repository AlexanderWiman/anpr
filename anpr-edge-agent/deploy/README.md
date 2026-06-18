# Deployment files

## Site profiles

Per-location RTSP settings live in `sites/<name>.env` (copy from `sites/*.env.example`).
Shared backend/YOLO settings in `.env.example`.

Workers choose site at start via `choose-site` (Windows: `start-anpr.cmd`, Linux/Mac: `start.sh`).

## Windows

| File | Purpose |
|------|---------|
| `env.production.windows.example` | Legacy single-file env for NSSM install |
| `nssm.exe` | *(you provide)* — [download NSSM](https://nssm.cc/download) |

```powershell
.\scripts\setup.ps1
.\scripts\install-windows-service.ps1
.\scripts\install-worker-shortcut.ps1
```

## Linux

| File | Purpose |
|------|---------|
| `anpr-edge-agent.service` | systemd unit |
| `env.production.example` | Legacy single-file env for systemd |

```bash
sudo ./scripts/install-systemd.sh
```
