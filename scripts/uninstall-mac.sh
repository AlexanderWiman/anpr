#!/usr/bin/env bash
# Remove macOS ANPR install (LaunchAgent + optional app copy).
set -euo pipefail

INSTALL_DIR="${HOME}/Applications/anpr-edge-agent"
SUPPORT_DIR="${HOME}/Library/Application Support/anpr-edge-agent"
PLIST_LABEL="com.anpr.edge-agent"
PLIST="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"
DESKTOP_CMD="${HOME}/Desktop/Start ANPR.command"

log() { echo "[uninstall] $*"; }

launchctl bootout "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || true
if [[ -f "$PLIST" ]]; then
  rm -f "$PLIST"
  log "Removed LaunchAgent"
fi

if [[ -f "$DESKTOP_CMD" ]]; then
  rm -f "$DESKTOP_CMD"
  log "Removed desktop shortcut"
fi

read -r -p "Remove application at $INSTALL_DIR? [y/N] " ans
if [[ "$ans" == "y" || "$ans" == "Y" ]]; then
  rm -rf "$INSTALL_DIR"
  log "Removed $INSTALL_DIR"
fi

read -r -p "Remove data/logs at $SUPPORT_DIR? [y/N] " ans
if [[ "$ans" == "y" || "$ans" == "Y" ]]; then
  rm -rf "$SUPPORT_DIR"
  log "Removed $SUPPORT_DIR"
fi

log "Done."
