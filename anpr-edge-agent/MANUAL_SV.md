# ANPR — Startmanual för anläggningar

Den här guiden beskriver hur ni sätter igång **ANPR Edge Agent** på platsdatorn vid anläggningen. All bildbehandling sker lokalt; endast registreringsnummer skickas till er centrala backend.

---

## Vad behöver ni innan ni börjar?

Be er IT-avdelning eller leverantör om följande **innan** installation:

| Uppgift | Exempel | Används till |
|--------|---------|--------------|
| **Site-ID** | `falun` | Identifierar anläggningen |
| **Kamera-ID** | `infart-1` | Vilken kamera som rapporterar |
| **Riktning** | `entry` eller `exit` | Infart / utfart |
| **RTSP-adress** | `rtsp://användare:lösenord@192.168.1.100:554/stream1` | IP-kamerans videoström |
| **Backend-URL** | `https://…` | Var händelser skickas |
| **Token** | (hemlig nyckel) | Autentisering mot backend |

**Hårdvara på plats**

- En dator (Windows rekommenderas) som står kvar och är påslagen
- Samma nätverk som IP-kameran
- Internet mot backend (kan vara instabilt — systemet köar lokalt)

**Program som installeras en gång (admin)**

- [Python 3.11+](https://www.python.org/downloads/) — kryssa i **"Add Python to PATH"**
- [FFmpeg](https://ffmpeg.org) — t.ex. `winget install Gyan.FFmpeg`
- Projektet `anpr-edge-agent` (zip eller git) på datorn

---

## Steg 1 — Kontrollera kameran

Innan ni installerar agenten, verifiera att videoströmmen fungerar:

1. Öppna **VLC** (eller liknande).
2. Öppna nätverksström med er **RTSP-adress**.
3. Ni ska se live-bild från kameran.

Om det inte fungerar i VLC fungerar det inte heller i ANPR — åtgärda nätverk, användarnamn/lösenord eller kamerainställningar först.

---

## Steg 2 — Installera (gör en gång, kräver admin)

### Windows (rekommenderat)

1. Kopiera mappen `anpr-edge-agent` till datorn, t.ex. `C:\anpr-edge-agent`.
2. Ladda ner **NSSM** från [nssm.cc](https://nssm.cc/download) och lägg `nssm.exe` i mappen `deploy\`.
3. Öppna **PowerShell som administratör**.
4. Kör:

```powershell
cd C:\anpr-edge-agent
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install-windows-service.ps1
```

Installationen lägger programmet här:

- Program: `C:\Program Files\anpr-edge-agent`
- Inställningar: `C:\ProgramData\anpr-edge-agent\.env`
- Loggar: `C:\ProgramData\anpr-edge-agent\logs\`

### Linux (valfritt)

```bash
cd /path/to/anpr-edge-agent
sudo ./scripts/install-systemd.sh
```

Inställningar: `/etc/anpr-edge-agent/env`

---

## Steg 3 — Konfigurera er anläggning

**En dator per anläggning:** kopiera `sites/falun.env.example` till `sites/falun.env` och fyll i RTSP-adress.

**En installer till flera anläggningar:** skapa en `sites/<namn>.env` per plats (se `sites/*.env.example`).

Redigera gemensamma inställningar i `.env.example` (backend-URL och token) — de slås ihop vid start.

**Windows (manuell start / genväg)**

```powershell
notepad .env.example
notepad sites\falun.env
```

**Windows (NSSM-tjänst)**

```powershell
notepad C:\ProgramData\anpr-edge-agent\.env
```

**Linux (systemd)**

```bash
sudo nano /etc/anpr-edge-agent/env
```

Fyll i minst dessa rader (i site-profilen eller `.env`):

```env
SITE_ID=ert-site-id
CAMERA_ID=ert-kamera-id
DIRECTION=entry

CAMERA_SOURCE=rtsp
CAMERA_RTSP_URL=rtsp://användare:lösenord@192.168.x.x:554/stream1

BACKEND_URL=https://er-backend-adress
ANPR_AGENT_TOKEN=er-hemliga-token

ANPR_PROVIDER=yolo_ocr
```

| Inställning | Förklaring |
|-------------|------------|
| `SITE_ID` | Unikt namn för anläggningen (små bokstäver, inga mellanslag) |
| `CAMERA_ID` | Namn på denna kamera, t.ex. `infart-1` |
| `DIRECTION` | `entry` = infart, `exit` = utfart |
| `CAMERA_RTSP_URL` | Hela RTSP-URL:en från kameran |
| `BACKEND_URL` | Bas-URL till molnet/centralen (utan `/api/...` i slutet) |
| `ANPR_AGENT_TOKEN` | Token ni fått från IT — dela aldrig publikt |
| `ANPR_PROVIDER` | Alltid `yolo_ocr` (YOLO + OCR) |

Spara filen och starta om tjänsten:

**Windows**

```powershell
nssm restart ANPREdgeAgent
```

**Linux**

```bash
sudo systemctl restart anpr-edge-agent
```

---

## Steg 4 — Skapa genväg för personal (valfritt men rekommenderat)

Kör **en gång** som admin:

```powershell
cd "C:\Program Files\anpr-edge-agent"
.\scripts\install-worker-shortcut.ps1
```

Det skapar genvägen **"Start ANPR"** på skrivbordet för alla användare.

---

## Steg 5 — Daglig användning (personal på plats)

### Om Windows-tjänsten körs (vanligast)

1. Datorn ska vara **påslagen** och uppkopplad.
2. Öppna webbläsaren på samma dator: **http://127.0.0.1:8080**
3. Kontrollera status:
   - **Kamera** — ska vara grön / ansluten
   - **Backend** — ska vara nåbar
4. Om systemet är stoppat: klicka **▶ Starta**.
5. Nya registreringsnummer visas under **Senaste händelser**.

Med `AGENT_AUTO_START=false` (standard) klickar personal **▶ Starta** i webbläsaren efter att de valt anläggning vid start.

### Om ni startar manuellt (utan tjänst / test)

1. Dubbelklicka **"Start ANPR"** på skrivbordet.
2. Välj anläggning om flera finns (t.ex. Falun, Borlänge).
2. Webbläsaren öppnas automatiskt.
3. **Lämna det svarta fönstret öppet** medan systemet ska vara aktivt.
4. Klicka **▶ Starta** i webbläsaren om det behövs.
5. Stäng fönstret när ni vill stänga av helt.

---

## Steg 6 — Kontrollera att allt fungerar

Öppna **http://127.0.0.1:8080** och kontrollera:

| Visar | Betyder |
|-------|---------|
| Kamera: ansluten | RTSP-ström fungerar |
| Backend: OK | Händelser kan skickas |
| Senaste händelser | Skyltar läses och levereras |

**Admin — loggar**

Windows:

```powershell
Get-Content C:\ProgramData\anpr-edge-agent\logs\agent.log -Tail 30 -Wait
```

Linux:

```bash
sudo journalctl -u anpr-edge-agent -f
```

---

## Enkel felsökning

| Problem | Åtgärd |
|---------|--------|
| Kamera röd / frånkopplad | Kontrollera RTSP i VLC, nätverk, ström till kamera, rätt URL i `.env` |
| Backend röd | Kontrollera internet, `BACKEND_URL` och `ANPR_AGENT_TOKEN` |
| Inga skyltar | Kontrollera kameravinkel, belysning och RTSP-adress i `sites/<anläggning>.env` |
| Händelser i kö men skickas inte | Backend nere — de skickas automatiskt när anslutningen återkommer |
| Dashboard öppnas inte | Kontrollera att tjänsten/agenten körs; prova starta om tjänsten |
| Efter omstart fungerar inget | Windows: kontrollera att tjänsten **ANPREdgeAgent** är startad (`services.msc`) |

Vid fortsatt problem: skicka senaste raderna från `agent.log` till IT tillsammans med er `SITE_ID` och `CAMERA_ID`.

---

## Viktiga adresser

| Vad | Adress |
|-----|--------|
| Dashboard (lokal) | http://127.0.0.1:8080 |
| Hälsokontroll (teknik) | http://127.0.0.1:8080/health |

Dashboard är endast tillgänglig på **samma dator** (säkerhetsstandard).

---

## Uppgradering

1. Ladda ner ny version av `anpr-edge-agent`.
2. Kör installskriptet igen (samma kommando som i Steg 2).
3. Er `.env` i ProgramData `/etc` behålls.
4. Starta om tjänsten.

---

## Snabbreferens — roller

| Roll | Gör |
|------|-----|
| **IT / admin** | Steg 1–4, konfigurera `.env`, installera tjänst |
| **Personal** | Öppna dashboard, Starta/Stoppa vid behov, lämna datorn på |
| **Support** | Läsa loggar, verifiera RTSP och backend |

Teknisk dokumentation (engelska, utvecklare): se [README.md](README.md).
