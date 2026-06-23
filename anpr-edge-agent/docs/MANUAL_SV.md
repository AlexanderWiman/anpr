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

Klicka **Installera**. Första gången tar några minuter (laddar ner AI-modell).

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

## Felsökning

| Problem | Åtgärd |
|---------|--------|
| Python eller ffmpeg saknas | Använd **Installera automatiskt** i guiden, eller **launch/Install-Prerequisites.cmd** / **scripts/install-prerequisites.sh** |
| Kamera röd | Kontrollera IP och inloggning (Tapo: Camera Account i appen) |
| Backend röd | Kontrollera internet och token med IT |
| Inga skyltar | Kameravinkel, belysning |

**Loggar (IT):**

- Mac: `~/Library/Application Support/anpr-edge-agent/logs/`
- Windows: `%LOCALAPPDATA%\anpr-edge-agent\data\logs\`

---

## Uppdateringar

**Uppdateringar hämtas inte automatiskt.** Varje dator har sin egen kopia i:

- Mac: `~/Applications/anpr-edge-agent`
- Windows: `%LOCALAPPDATA%\anpr-edge-agent`

När det finns en ny version:

1. Ladda ner **ny ZIP** från GitHub och packa upp (ersätt gammal mapp eller lägg i ny)
2. Dubbelklicka **Install ANPR** / **launch/Installer.cmd** igen
3. På välkomststeget: klicka **Uppdatera nu**

Kamera, token och övriga inställningar **behålls** — bara programfilerna och Python-paketen uppdateras.

IT kan skicka ut ny ZIP till anläggningarna och be personal köra steg 2–3.

---

## Avancerat (IT)

Se [DEPLOY.md](DEPLOY.md) för manuell installation (systemd, Windows-tjänst, macOS LaunchAgent).
