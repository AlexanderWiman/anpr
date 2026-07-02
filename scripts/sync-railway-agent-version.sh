#!/usr/bin/env bash
# Push ANPR_AGENT_LATEST_VERSION to Railway (manual run from dev machine).
#
# Usage:
#   export RAILWAY_TOKEN=...   # from Railway → Project → Settings → Tokens
#   ./scripts/sync-railway-agent-version.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INIT="$ROOT/src/__init__.py"

if [ -z "${RAILWAY_TOKEN:-}" ] && [ -z "${RAILWAY_API_TOKEN:-}" ]; then
  echo "Set RAILWAY_TOKEN or RAILWAY_API_TOKEN" >&2
  exit 1
fi

VERSION=$(grep -E '^__version__\s*=' "$INIT" | sed -E 's/.*"([^"]+)".*/\1/')
if [ -z "$VERSION" ]; then
  echo "Could not read version from $INIT" >&2
  exit 1
fi

DOWNLOAD_URL="${ANPR_AGENT_DOWNLOAD_URL:-https://github.com/AlexanderWiman/anpr/archive/refs/heads/main.zip}"
PROJECT_ID="${RAILWAY_PROJECT_ID:-cd64c4cd-2eba-4cd5-b258-bb71274bdb50}"

if ! command -v railway >/dev/null 2>&1; then
  echo "Install Railway CLI: npm install -g @railway/cli" >&2
  exit 1
fi

echo "Setting ANPR_AGENT_LATEST_VERSION=$VERSION on Railway backend..."
railway variable set \
  "ANPR_AGENT_LATEST_VERSION=$VERSION" \
  "ANPR_AGENT_DOWNLOAD_URL=$DOWNLOAD_URL" \
  --service backend \
  --environment production \
  --project "$PROJECT_ID"

echo "Done. Edge installers will offer version $VERSION."
