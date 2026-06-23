#!/usr/bin/env bash
# Run ANPR edge agent (used by LaunchAgent and manual starts on macOS).
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SUPPORT_DIR="${HOME}/Library/Application Support/anpr-edge-agent"

cd "$INSTALL_DIR"

if [[ ! -f "${SUPPORT_DIR}/.env" ]]; then
  if [[ -x "${INSTALL_DIR}/scripts/choose-site.sh" ]]; then
  ANPR_SITE_PROFILE="${ANPR_SITE_PROFILE:-}" "${INSTALL_DIR}/scripts/choose-site.sh" || true
  fi
  if [[ -f ".env" ]]; then
    mkdir -p "${SUPPORT_DIR}"
    cp ".env" "${SUPPORT_DIR}/.env"
  fi
fi

if [[ ! -f "${SUPPORT_DIR}/.env" ]]; then
  echo "Config missing: ${SUPPORT_DIR}/.env"
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "Virtual environment missing. Run: ${INSTALL_DIR}/scripts/install-mac.sh"
  exit 1
fi

# shellcheck disable=SC1091
source ".venv/bin/activate"
export PYTHONUNBUFFERED=1
export PYTHONPATH="${INSTALL_DIR}"
exec python -m src.main
