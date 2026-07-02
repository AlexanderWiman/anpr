#!/usr/bin/env bash
# First-time setup: Python venv, dependencies, YOLO model.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== ANPR Edge Agent — setup ==="

if [ ! -d ".venv" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt -r requirements-ai.txt -r requirements-ocr.txt

if [ ! -f "models/plate_yolov8.pt" ]; then
  echo "Downloading YOLO plate model..."
  ./scripts/download-yolo-model.sh
fi

if [ ! -f ".env" ]; then
  if compgen -G "sites/*.env" > /dev/null; then
    echo "Choose site profile on first start (./scripts/start.sh)."
  else
    cp .env.example .env
    echo "Created .env — copy sites/<site>.env.example to sites/<site>.env and configure."
  fi
fi

echo ""
echo "Setup complete."
echo "  1. Copy sites/falun.env.example to sites/falun.env (edit RTSP URL + token in .env)"
echo "  2. Run: ./scripts/start.sh"
