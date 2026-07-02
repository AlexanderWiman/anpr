#!/usr/bin/env bash
#
# Uninstall ANPR Edge Agent systemd service.
# Does NOT remove /var/lib/anpr-edge-agent data by default.
#
# Usage:
#   sudo ./scripts/uninstall-systemd.sh
#   sudo ./scripts/uninstall-systemd.sh --purge-data
#
set -euo pipefail

SERVICE_NAME="anpr-edge-agent"
INSTALL_DIR="/opt/anpr-edge-agent"
CONFIG_DIR="/etc/anpr-edge-agent"
DATA_DIR="/var/lib/anpr-edge-agent"
SERVICE_USER="anpr-agent"
PURGE_DATA=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --purge-data) PURGE_DATA=true; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true
rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload

rm -rf "$INSTALL_DIR"
rm -rf "$CONFIG_DIR"

if [[ "$PURGE_DATA" == true ]]; then
  rm -rf "$DATA_DIR"
  echo "Removed data: $DATA_DIR"
fi

if id "$SERVICE_USER" &>/dev/null; then
  userdel "$SERVICE_USER" 2>/dev/null || true
fi

echo "Uninstalled $SERVICE_NAME"
echo "Data kept at $DATA_DIR (use --purge-data to remove)"
