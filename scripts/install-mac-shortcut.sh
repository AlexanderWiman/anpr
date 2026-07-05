#!/usr/bin/env bash
# Create a Desktop shortcut to start ANPR (macOS).
set -euo pipefail

INSTALL_DIR="${ANPR_INSTALL_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SHORTCUT_NAME="${ANPR_SHORTCUT_NAME:-Start ANPR}"
DESKTOP="${HOME}/Desktop"
APP_PATH="${DESKTOP}/${SHORTCUT_NAME}.app"
LEGACY_CMD="${DESKTOP}/${SHORTCUT_NAME}.command"
ICON_SRC="${INSTALL_DIR}/assets/icons/anpr.icns"
LAUNCHER="${APP_PATH}/Contents/MacOS/launcher"

if [[ ! -d "$INSTALL_DIR" ]]; then
  echo "Install dir not found: $INSTALL_DIR"
  exit 1
fi

rm -f "$LEGACY_CMD"
rm -rf "$APP_PATH"
mkdir -p "$APP_PATH/Contents/MacOS" "$APP_PATH/Contents/Resources"

if [[ -f "$ICON_SRC" ]]; then
  cp "$ICON_SRC" "$APP_PATH/Contents/Resources/AppIcon.icns"
fi

cat > "$APP_PATH/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>launcher</string>
  <key>CFBundleIdentifier</key>
  <string>com.anpr.edge-agent.dashboard</string>
  <key>CFBundleName</key>
  <string>${SHORTCUT_NAME}</string>
  <key>CFBundleDisplayName</key>
  <string>${SHORTCUT_NAME}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

cat > "$LAUNCHER" <<EOF
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

if [[ -x "./scripts/wait-for-agent.sh" ]]; then
  ./scripts/wait-for-agent.sh || true
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

chmod +x "$LAUNCHER"

echo "Desktop shortcut created:"
echo "  $APP_PATH"
echo ""
echo "Double-click '${SHORTCUT_NAME}' to choose site and open the dashboard."
