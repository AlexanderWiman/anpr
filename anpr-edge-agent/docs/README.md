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

## Utvecklare

```bash
./scripts/setup.sh && ./scripts/start.sh
```

Se [DEPLOY.md](DEPLOY.md) för avancerad installation.
