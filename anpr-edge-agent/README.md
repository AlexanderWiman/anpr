# ANPR Edge Agent

> **Personal på anläggning:** [MANUAL_SV.md](MANUAL_SV.md)

## Installation (3 steg)

1. **Ladda ner** projektet från GitHub (Code → Download ZIP) och packa upp
2. **Dubbelklicka** på `Installer` (`Installer.command` på Mac, `Installer.cmd` på Windows)
3. Fyll i **anläggning**, **kamera-IP** och **token** → klicka **Installera och starta**

Klart. Systemet startar själv vid omstart. Använd genvägen **ANPR** på skrivbordet för att öppna dashboarden.

**Krav:** Python 3.11+ ([python.org](https://www.python.org/downloads/)), FFmpeg (`brew install ffmpeg` / `winget install Gyan.FFmpeg`)

---

Local service at the IP camera site: RTSP capture, YOLO+OCR, events to central backend.

## För IT / utvecklare

```bash
./scripts/setup.sh && ./scripts/start.sh
```

See [deploy/README.md](deploy/README.md) for systemd / advanced installs.
