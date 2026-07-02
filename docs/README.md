# Dokumentation — ANPR Edge Agent

| Dokument | Målgrupp |
|----------|----------|
| [MANUAL_SV.md](MANUAL_SV.md) | Personal på anläggning (installation & daglig drift) |
| [DEPLOY.md](DEPLOY.md) | IT (systemd, Windows-tjänst, manuell install) |

## Snabbstart

**Mac:** dubbelklicka **Install ANPR** i Finder  
**Windows:** dubbelklicka **launch/Installer.cmd**

## Mappstruktur

| Mapp / fil | Innehåll |
|------------|----------|
| **Install ANPR.app** | Mac-installation (personal) |
| **launch/** | Windows-installation och reserv-startare |
| **installer/** | Installationsguiden (webb) |
| **src/** | ANPR-programmet |
| **scripts/** | IT-skript (manuell install, avinstallera m.m.) |
| **sites/** | Anläggningsprofiler (`.env.example`) |
| **deploy/** | Konfigurationsfiler för systemd, LaunchAgent m.m. |
| **tests/** | Tester |

## Utvecklare / IT (manuell körning)

```bash
cp sites/falun.env.example sites/falun.env   # sätt CAMERA_RTSP_URL
./scripts/setup.sh
./scripts/choose-site.sh                     # skapar .env med RTSP
./scripts/start.sh
```

Testa backend-API: `./scripts/send-test-event.sh DMY009`

Se [DEPLOY.md](DEPLOY.md) för systemd / Windows-tjänst.
