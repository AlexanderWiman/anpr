#!/usr/bin/env bash
# Regenerate anpr.icns and anpr.ico from assets/icons/anpr-icon-1024.png
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/assets/icons/anpr-icon-1024.png"
DEST="$ROOT/assets/icons"
ICONSET="$DEST/anpr.iconset"

if [[ ! -f "$SRC" ]]; then
  echo "Missing source icon: $SRC" >&2
  exit 1
fi

rm -rf "$ICONSET"
mkdir -p "$ICONSET"

for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$SRC" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" "$SRC" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done

iconutil -c icns "$ICONSET" -o "$DEST/anpr.icns"
rm -rf "$ICONSET"

VENV="$(mktemp -d)/venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install -q pillow
"$VENV/bin/python" <<PY
from pathlib import Path
from PIL import Image

src = Path("$SRC")
img = Image.open(src).convert("RGBA")
sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save("$DEST/anpr.ico", format="ICO", sizes=sizes)
PY
rm -rf "$(dirname "$VENV")"

echo "Built $DEST/anpr.icns and $DEST/anpr.ico"
