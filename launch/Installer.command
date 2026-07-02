#!/bin/bash
# Reserv-installer — öppnar Terminal + webbläsare (Mac)
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${ANPR_INSTALLER_PORT:-17880}"
osascript <<EOF
tell application "Terminal"
  activate
  do script "cd '$(printf '%s' "$DIR" | sed "s/'/'\\\\''/g")' && export ANPR_INSTALLER_PORT=$PORT ANPR_INSTALLER_WAITING=1 ANPR_INSTALLER_OPEN=open && python3 -m installer; echo ''; echo 'Tryck Enter för att stänga...'; read"
end tell
EOF
