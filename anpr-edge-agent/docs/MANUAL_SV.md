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
| I **Finder**: dubbelklicka **Install ANPR** | Dubbelklicka **launch/Installer.cmd** |
| Reserv (Terminal): **launch/Installer.command** | Förutsättningar: **launch/Install-Prerequisites.cmd** |

En **installationsguide** öppnas (som när man installerar ett vanligt program): Välkommen → Anläggning → Kamera → Token → Installera → Klart.

**Viktigt (Mac):** Öppna från **Finder**, inte från Cursor.

### 3. Fyll i formuläret

| Fält | Exempel |
|------|---------|
| **Anläggning** | Falun |
| **Kamera-IP** | `192.168.0.96` |
| **Kameratyp** | Tapo (TP-Link) eller annan RTSP |
| **Kamerakonto** | Användarnamn + lösenord (Tapo Camera Account) |
| **Backend-token** | (få från IT) |

Klicka **Installera**. Första gången tar **10–15 minuter** (laddar ner AI-komponenter från internet). Guiden kan se ut att stå stilla — det är normalt, stäng inte fönstret.

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
| **Kameratyp** | Tapo med RTSP-konto |

**Program som behövs** — guiden kan installera det mesta automatiskt:

| Mac | Windows |
|-----|---------|
| Dubbelklicka **Install ANPR** — följ steg 1 | Dubbelklicka **launch/Installer.cmd** |
| Saknas Homebrew? **scripts/install-prerequisites.sh** | Saknas winget? **launch/Install-Prerequisites.cmd** |

Guiden visar status för **Python** och **ffmpeg** med knapp **Installera automatiskt** (via Homebrew eller winget).

---

## Konfiguration (IT)

**Windows — redigera bara den här filen:**

`%LOCALAPPDATA%\anpr-edge-agent\data\.env`

Ignorera `%LOCALAPPDATA%\anpr-edge-agent\.env` om den finns (gammal kopia). Starta om med `run-agent.cmd` efter ändringar.

**Mac:**

`~/Library/Application Support/anpr-edge-agent/.env`

---

## Felsökning

| Problem | Åtgärd |
|---------|--------|
| Python eller ffmpeg saknas | Använd **Installera automatiskt** i guiden, eller **launch/Install-Prerequisites.cmd** / **scripts/install-prerequisites.sh** |
| Windows: «Python hittades inte» / Microsoft Store | Kör **launch/Installer.cmd** igen (ny version ignorerar Store-alias). Eller stäng av **python.exe** under Inställningar → Appar → Avancerade appinställningar → **Appkörningsalias** |
| Windows: pip / paketinstallation misslyckas | Stäng guiden, radera mappen `%LOCALAPPDATA%\anpr-edge-agent\.venv` och kör **Installer.cmd** igen |
| Kamera röd / funkar i VLC men inte i ANPR | Kontrollera `CAMERA_RTSP_URL` i `data\.env` (samma som i VLC). Sätt `RTSP_TRANSPORT=tcp`. Klicka **Starta** i dashboarden. Kolla att **ffmpeg** är installerat (guiden → Installera automatiskt). Dashboarden visar inte livevideo — bara status **OK** och tid för senaste bild |
| Backend röd / «Fel token» | Kontrollera token med IT och spara om via **Install ANPR** → guiden |
| 127.0.0.1 nekade anslutning | Använd genvägen **ANPR** på skrivbordet (inte en gammal webbläsargenväg). Kör `%LOCALAPPDATA%\anpr-edge-agent\scripts\diagnose-windows.cmd` eller `run-agent.cmd` och lämna fönstret öppet. Logg: `data\logs\agent-startup.log` |
| Inga skyltar | Kameravinkel, belysning |

**Loggar (IT):**

- Mac: `~/Library/Application Support/anpr-edge-agent/logs/`
- Windows: `%LOCALAPPDATA%\anpr-edge-agent\data\logs\`

---

## Fjärrövervakning (IT)

Agenten skickar en **heartbeat** till backend var 60:e sekund (så fort programmet kör, även om läsning är stoppad). Därmed kan IT se om verkstadsdatorn, kameran och backend-länken fungerar — utan att logga in på platsdatorn.

- **Railway HTTP Logs:** sök `borlange heartbeat` eller `@path:/api/anpr/sites/borlange/heartbeat` — en träff per minut ≈ datorn är igång.
- **Staff-app (planerat):** statusruta på anläggningsdashboard när backend-endpointen är utbyggd (se `docs/BACKEND_HEARTBEAT.md`).

Inställningar i `data\.env`:

- `HEARTBEAT_ENABLED=true` (standard)
- `HEARTBEAT_INTERVAL_SECONDS=60`

---

## Uppdateringar

**Personal behöver inte ladda ner ZIP eller förstå GitHub.**

När IT säger att det finns en uppdatering:

1. Dubbelklicka **Install ANPR** (samma som vid första installationen)
2. Klicka **Uppdatera automatiskt**

Klart. Programmet laddas ner från internet, installeras om och startar igen. **Kamera, token och inställningar behålls.**

Om knappen inte syns är datorn redan uppdaterad.

### För IT

**Släpp ny version:**

1. Höj `__version__` i `anpr-edge-agent/src/__init__.py`
2. Pusha till `main` på GitHub (`AlexanderWiman/anpr`)
3. GitHub Actions uppdaterar automatiskt `ANPR_AGENT_LATEST_VERSION` på Railway-backend
4. Be personal: **Install ANPR** → **Uppdatera automatiskt**

**Engångsinställning (GitHub):** lägg samma `RAILWAY_TOKEN` som i `auto-care-joy` under **anpr**-repots Secrets → Actions.

Manuellt från utvecklardator:

```bash
export RAILWAY_TOKEN=...
./anpr-edge-agent/scripts/sync-railway-agent-version.sh
```

Om Railway-variablerna saknas faller installern tillbaka till GitHub `main` direkt.

Se även backend-dokumentationen `ANPR_EDGE_AGENT.md`.

---

## Avancerat (IT)

Se [DEPLOY.md](DEPLOY.md) för manuell installation (systemd, Windows-tjänst, macOS LaunchAgent).
