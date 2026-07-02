#!/usr/bin/env bash
# Send a test ANPR event via the real backend API (same path as the edge agent).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a && source .env && set +a
fi

PLATE="${1:-TEST001}"
SITE="${SITE_ID:-falun}"
CAMERA="${CAMERA_ID:-entrance-1}"
DIRECTION="${DIRECTION:-entry}"

if [ -z "${BACKEND_URL:-}" ] || [ -z "${ANPR_AGENT_TOKEN:-}" ]; then
  echo "Set BACKEND_URL and ANPR_AGENT_TOKEN in .env"
  exit 1
fi

CAPTURED="$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"
URL="${BACKEND_URL%/}/api/anpr/events"

echo "POST $URL  plate=$PLATE  site=$SITE"
curl -sS -X POST "$URL" \
  -H "Authorization: Bearer $ANPR_AGENT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "User-Agent: anpr-edge-agent/1.0.0" \
  -d "{
    \"siteId\": \"$SITE\",
    \"cameraId\": \"$CAMERA\",
    \"plate\": \"$PLATE\",
    \"confidence\": 0.91,
    \"capturedAt\": \"$CAPTURED\",
    \"provider\": \"yolo_ocr\",
    \"direction\": \"$DIRECTION\",
    \"snapshotBase64\": null
  }"
echo ""
