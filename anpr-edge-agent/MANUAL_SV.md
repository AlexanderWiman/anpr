# ANPR — Startmanual för anläggningar

All bildbehandling sker lokalt. Endast registreringsnummer skickas till er centrala backend.

---

## Installation (personal)

### 1. Ladda ner

1. Gå till projektet på **GitHub**
2. Klicka **Code** → **Download ZIP**
3. Packa upp zip-filen (dubbelklicka)

### 2. Installera

| Mac | Windows |
|-----|---------|
| Dubbelklicka **Installer.command** | Dubbelklicka **Installer.cmd** |

*(Om Mac frågar: högerklicka → Öppna första gången.)*

### 3. Fyll i formuläret

| Fält | Exempel |
|------|---------|
| **Anläggning** | Falun |
| **Kamera-IP** | `192.168.0.96` |
| **Kameratyp** | IP Webcam eller RTSP |
| **Backend-token** | (få från IT) |

Klicka **Installera och starta**. Första gången tar några minuter (laddar ner AI-modell).

### 4. Klart

- Webbläsaren öppnas automatiskt
- ANPR läser skyltar från kameran
- Vid omstart av datorn startar systemet själv
- Genvägen **ANPR** på skrivbordet öppnar dashboarden

---

## Daglig användning

1. Datorn ska vara påslagen
2. Dubbelklicka **ANPR** på skrivbordet (eller öppna http://127.0.0.1:8080)
3. Kontrollera att **Kamera** och **Backend** är gröna
4. Nya registreringsnummer visas under **Senaste händelser**

---

## Innan installation — be IT om

| Uppgift | Exempel |
|--------|---------|
| **Backend-token** | Hemlig nyckel |
| **Kamera-IP** | `192.168.0.96` |
| **Kameratyp** | IP Webcam-app eller RTSP-kamera |

**Program som behövs (IT installerar en gång):**

- [Python 3.11+](https://www.python.org/downloads/) — kryssa i **Add Python to PATH** (Windows)
- [FFmpeg](https://ffmpeg.org) — Mac: `brew install ffmpeg`, Windows: `winget install Gyan.FFmpeg`

---

## Felsökning

| Problem | Åtgärd |
|---------|--------|
| Python saknas | Installera från python.org, kör Installer igen |
| Kamera röd | Kontrollera IP i VLC / webbläsare (`http://IP:8080`) |
| Backend röd | Kontrollera internet och token med IT |
| Inga skyltar | Kameravinkel, belysning |

**Loggar (IT):**

- Mac: `~/Library/Application Support/anpr-edge-agent/logs/`
- Windows: `%LOCALAPPDATA%\anpr-edge-agent\data\logs\`

---

## Avancerat (IT)

Manuell installation: `scripts/install-mac.sh`, `scripts/install-windows-service.ps1`, `scripts/install-systemd.sh`
