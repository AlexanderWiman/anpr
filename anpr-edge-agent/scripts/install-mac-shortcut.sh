#!/usr/bin/env bash
# Create a Desktop shortcut to start ANPR (macOS).
set -euo pipefail

INSTALL_DIR="${ANPR_INSTALL_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SHORTCUT_NAME="${ANPR_SHORTCUT_NAME:-Start ANPR}"
DESKTOP="${HOME}/Desktop"
CMD_PATH="${DESKTOP}/${SHORTCUT_NAME}.command"

if [[ ! -d "$INSTALL_DIR" ]]; then
  echo "Install dir not found: $INSTALL_DIR"
  exit 1
fi

cat > "$CMD_PATH" <<EOF
#!/bin/bash
cd "${INSTALL_DIR}"
export ANPR_INSTALL_DIR="${INSTALL_DIR}"

if [[ -x "./scripts/choose-site.sh" ]]; then
  ./scripts/choose-site.sh
  if [[ -f .env ]]; then
    mkdir -p "\${HOME}/Library/Application Support/anpr-edge-agent"
    cp .env "\${HOME}/Library/Application Support/anpr-edge-agent/.env"
  fi
fi

open "http://127.0.0.1:\${HEALTH_PORT:-8080}"

if launchctl print "gui/\$(id -u)/com.anpr.edge-agent" &>/dev/null; then
  echo ""
  echo "  ANPR körs redan (LaunchAgent)."
  echo "  Öppnade webbläsaren — klicka Starta om det behövs."
  echo ""
  read -r -p "Tryck Enter för att stänga..."
  exit 0
fi

echo ""
echo "  ANPR Edge Agent"
echo "  Lämna detta fönster öppet medan systemet kör."
echo ""

export PYTHONUNBUFFERED=1
export PYTHONPATH="${INSTALL_DIR}"
"${INSTALL_DIR}/.venv/bin/python" -m src.main
EOF

chmod +x "$CMD_PATH"

echo "Desktop shortcut created:"
echo "  $CMD_PATH"
echo ""
echo "Double-click '${SHORTCUT_NAME}' to choose site and open the dashboard."
