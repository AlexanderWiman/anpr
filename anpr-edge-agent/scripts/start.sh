#!/usr/bin/env bash
# Start ANPR edge agent (Mac/Linux)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo "Run ./scripts/setup.sh first."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

./scripts/choose-site.sh

PORT="${HEALTH_PORT:-8080}"
if lsof -i ":$PORT" -t >/dev/null 2>&1; then
  echo "Port $PORT in use. Stop with: kill \$(lsof -i :$PORT -t)"
  exit 1
fi

echo ""
echo "  ANPR Edge Agent"
echo "  Open: http://127.0.0.1:$PORT"
echo ""

export PYTHONUNBUFFERED=1
export PYTHONPATH="$PWD"
python -m src.main
