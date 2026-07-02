#!/usr/bin/env bash
# Wait for ANPR dashboard on 127.0.0.1:8080; optionally start the agent.
set -euo pipefail

INSTALL_DIR="${ANPR_INSTALL_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
PORT="${HEALTH_PORT:-8080}"
URL="http://127.0.0.1:${PORT}/api/version"
TIMEOUT="${ANPR_AGENT_WAIT_SECONDS:-120}"
START_IF_DOWN="${ANPR_AGENT_START_IF_DOWN:-1}"

agent_up() {
  curl -sf --max-time 2 "$URL" >/dev/null 2>&1
}

if agent_up; then
  exit 0
fi

if [[ "$START_IF_DOWN" == "1" ]]; then
  echo "Startar ANPR..."
  if launchctl print "gui/$(id -u)/com.anpr.edge-agent" &>/dev/null; then
    launchctl kickstart -k "gui/$(id -u)/com.anpr.edge-agent" 2>/dev/null || true
  elif [[ -x "${INSTALL_DIR}/scripts/run-agent.sh" ]]; then
    nohup bash "${INSTALL_DIR}/scripts/run-agent.sh" \
      >>"${HOME}/Library/Application Support/anpr-edge-agent/logs/manual-start.log" 2>&1 &
  fi
fi

deadline=$((SECONDS + TIMEOUT))
while (( SECONDS < deadline )); do
  if agent_up; then
    exit 0
  fi
  sleep 1
done

echo ""
echo "ANPR svarar inte på http://127.0.0.1:${PORT}"
echo ""
echo "Prova:"
echo "  ${INSTALL_DIR}/scripts/run-agent.sh"
echo ""
echo "Logg:"
echo "  ${HOME}/Library/Application Support/anpr-edge-agent/logs/launchd-stderr.log"
exit 1
