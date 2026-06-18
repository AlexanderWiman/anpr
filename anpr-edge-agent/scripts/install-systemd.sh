#!/usr/bin/env bash
#
# Install ANPR Edge Agent as a systemd service on Linux.
#
# Usage (run as root):
#   sudo ./scripts/install-systemd.sh
#
# Options:
#   --install-dir /opt/anpr-edge-agent   Application directory
#   --from-dir /path/to/anpr-edge-agent    Source (default: repo root)
#   --no-start                           Enable but do not start service
#
set -euo pipefail

INSTALL_DIR="/opt/anpr-edge-agent"
CONFIG_DIR="/etc/anpr-edge-agent"
DATA_DIR="/var/lib/anpr-edge-agent"
SERVICE_USER="anpr-agent"
SERVICE_NAME="anpr-edge-agent"
FROM_DIR=""
NO_START=false

log() { echo "[install] $*"; }
die() { echo "[install] ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    --from-dir) FROM_DIR="$2"; shift 2 ;;
    --no-start) NO_START=true; shift ;;
    -h|--help)
      grep '^#' "$0" | tail -n +3 | sed 's/^# \?//'
      exit 0
      ;;
    *) die "Unknown option: $1" ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  die "Run as root: sudo $0"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FROM_DIR="${FROM_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"

[[ -f "$FROM_DIR/requirements.txt" ]] || die "Invalid source dir: $FROM_DIR"
command -v python3 >/dev/null || die "python3 not found"
command -v systemctl >/dev/null || die "systemctl not found (systemd required)"

if ! command -v ffmpeg >/dev/null; then
  log "WARNING: ffmpeg not found — install for RTSP support:"
  log "  apt install ffmpeg   (Debian/Ubuntu)"
  log "  dnf install ffmpeg   (Fedora/RHEL)"
fi

# --- Service user ---
if ! id "$SERVICE_USER" &>/dev/null; then
  log "Creating system user: $SERVICE_USER"
  useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# --- Application files ---
log "Installing application to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
rsync -a --delete \
  --exclude '.venv' \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude 'storage' \
  --exclude 'logs' \
  --exclude '.env' \
  --exclude '.env.dev' \
  "$FROM_DIR/" "$INSTALL_DIR/"

# --- Python venv ---
if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
  log "Creating virtual environment"
  python3 -m venv "$INSTALL_DIR/.venv"
fi

log "Installing Python dependencies"
"$INSTALL_DIR/.venv/bin/pip" install -q --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"

# --- Data directories ---
log "Creating data directories in $DATA_DIR"
mkdir -p "$DATA_DIR/storage/frames" "$DATA_DIR/storage/events" "$DATA_DIR/logs"
chown -R "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"
chmod 750 "$DATA_DIR"

# --- Configuration ---
log "Installing config to $CONFIG_DIR/env"
mkdir -p "$CONFIG_DIR"
if [[ ! -f "$CONFIG_DIR/env" ]]; then
  cp "$INSTALL_DIR/deploy/env.production.example" "$CONFIG_DIR/env"
  chmod 640 "$CONFIG_DIR/env"
  chown root:"$SERVICE_USER" "$CONFIG_DIR/env"
  log "Created $CONFIG_DIR/env — EDIT BEFORE STARTING (RTSP URL, token, site ID)"
else
  log "Keeping existing $CONFIG_DIR/env"
fi

# --- Ownership ---
chown -R root:"$SERVICE_USER" "$INSTALL_DIR"
chmod -R g+rX "$INSTALL_DIR"

# --- systemd unit ---
log "Installing systemd unit"
cp "$INSTALL_DIR/deploy/anpr-edge-agent.service" "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

if [[ "$NO_START" == true ]]; then
  log "Service enabled. Edit $CONFIG_DIR/env then run:"
  log "  sudo systemctl start $SERVICE_NAME"
else
  log "Starting $SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"
  sleep 2
  systemctl --no-pager status "$SERVICE_NAME" || true
fi

cat <<EOF

Installation complete.

  Config:   $CONFIG_DIR/env
  Data:     $DATA_DIR
  Health:   curl http://127.0.0.1:8080/health

Commands:
  sudo systemctl status  $SERVICE_NAME
  sudo systemctl restart $SERVICE_NAME
  sudo journalctl -u $SERVICE_NAME -f

EOF
