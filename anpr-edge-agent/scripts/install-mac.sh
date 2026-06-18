#!/usr/bin/env bash
#
# Install ANPR Edge Agent on macOS (user-level, no admin required).
#
# Installs to:  ~/Applications/anpr-edge-agent
# Config/data:  ~/Library/Application Support/anpr-edge-agent
# Auto-start:   ~/Library/LaunchAgents/com.anpr.edge-agent.plist
#
# Usage:
#   ./scripts/install-mac.sh
#   ./scripts/install-mac.sh --no-service    # skip LaunchAgent
#   ./scripts/install-mac.sh --from-dir /path/to/anpr-edge-agent
#
set -euo pipefail

INSTALL_DIR="${HOME}/Applications/anpr-edge-agent"
SUPPORT_DIR="${HOME}/Library/Application Support/anpr-edge-agent"
PLIST_LABEL="com.anpr.edge-agent"
FROM_DIR=""
NO_SERVICE=false
INSTALL_SHORTCUT=true

log() { echo "[install] $*"; }
die() { echo "[install] ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    --from-dir) FROM_DIR="$2"; shift 2 ;;
    --no-service) NO_SERVICE=true; shift ;;
    --no-shortcut) INSTALL_SHORTCUT=false; shift ;;
    -h|--help)
      sed -n '3,14p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) die "Unknown option: $1" ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FROM_DIR="${FROM_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
[[ -f "$FROM_DIR/requirements.txt" ]] || die "Invalid source dir: $FROM_DIR"

command -v python3 >/dev/null || die "python3 not found — install from https://www.python.org/downloads/"

if ! command -v ffmpeg >/dev/null; then
  log "WARNING: ffmpeg not in PATH. Install with: brew install ffmpeg"
fi

log "Installing from $FROM_DIR"
log "Target: $INSTALL_DIR"

mkdir -p "$INSTALL_DIR" "$SUPPORT_DIR/logs" "$SUPPORT_DIR/storage"

rsync -a --delete \
  --exclude '.venv' \
  --exclude '.env' \
  --exclude '.git' \
  --exclude 'storage' \
  --exclude 'logs' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude 'models/*.pt' \
  "$FROM_DIR/" "$INSTALL_DIR/"

chmod +x "$INSTALL_DIR"/scripts/*.sh 2>/dev/null || true

log "Running setup (venv + YOLO model)..."
(
  cd "$INSTALL_DIR"
  ./scripts/setup.sh
)

if [[ -f "$FROM_DIR/.env" ]]; then
  cp "$FROM_DIR/.env" "$SUPPORT_DIR/.env"
  log "Copied existing .env to Application Support"
elif [[ ! -f "$SUPPORT_DIR/.env" ]]; then
  log ""
  log "Next: configure site profile"
  log "  cp $INSTALL_DIR/sites/falun.env.example $INSTALL_DIR/sites/falun.env"
  log "  edit sites/falun.env (RTSP URL) and .env.example (BACKEND_URL, token)"
  log "  then run: $INSTALL_DIR/scripts/choose-site.sh"
  log ""
fi

if [[ "$NO_SERVICE" = false ]]; then
  PLIST_DST="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"
  mkdir -p "${HOME}/Library/LaunchAgents"
  sed \
    -e "s|__INSTALL_DIR__|${INSTALL_DIR}|g" \
    -e "s|__SUPPORT_DIR__|${SUPPORT_DIR}|g" \
    "$INSTALL_DIR/deploy/com.anpr.edge-agent.plist" > "$PLIST_DST"

  launchctl bootout "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
  launchctl enable "gui/$(id -u)/${PLIST_LABEL}"
  log "LaunchAgent installed — agent starts at login"
  log "Logs: $SUPPORT_DIR/logs/launchd-stdout.log"
else
  log "Skipped LaunchAgent (--no-service)"
fi

if [[ "$INSTALL_SHORTCUT" = true ]]; then
  ANPR_INSTALL_DIR="$INSTALL_DIR" "$INSTALL_DIR/scripts/install-mac-shortcut.sh"
fi

if [[ ! -f "$SUPPORT_DIR/.env" ]] && [[ -t 0 ]]; then
  read -r -p "Configure site profile now? [Y/n] " ans
  if [[ "$ans" != "n" && "$ans" != "N" ]]; then
    (cd "$INSTALL_DIR" && ./scripts/choose-site.sh)
    if [[ -f "$INSTALL_DIR/.env" ]]; then
      cp "$INSTALL_DIR/.env" "$SUPPORT_DIR/.env"
      log "Saved config to $SUPPORT_DIR/.env"
    fi
  fi
fi

log ""
log "Done."
log "  Dashboard: http://127.0.0.1:8080"
log "  Desktop:   Start ANPR"
log "  Stop:      launchctl bootout gui/$(id -u)/${PLIST_LABEL}"
