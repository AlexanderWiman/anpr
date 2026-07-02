#!/usr/bin/env bash
# Download YOLOv8 license plate detection model (~6 MB)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/models/plate_yolov8.pt"
URL="https://huggingface.co/Koushim/yolov8-license-plate-detection/resolve/main/best.pt"

mkdir -p "$ROOT/models"

if [[ -f "$DEST" ]]; then
  echo "Model already exists: $DEST ($(du -h "$DEST" | cut -f1))"
  exit 0
fi

echo "Downloading YOLO plate model to $DEST ..."
curl -fsSL "$URL" -o "$DEST"
echo "Done: $DEST ($(du -h "$DEST" | cut -f1))"
