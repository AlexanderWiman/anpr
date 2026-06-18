#!/usr/bin/env bash
# Merge shared .env.example with a site profile into .env
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

merge_profile() {
  local site_file="$1"
  if [ ! -f ".env.example" ]; then
    echo "Missing .env.example"
    exit 1
  fi
  if [ ! -f "$site_file" ]; then
    echo "Missing site profile: $site_file"
    exit 1
  fi
  {
    cat .env.example
    echo ""
    echo "# Site profile: $site_file"
    cat "$site_file"
  } > .env
  echo "Using $site_file"
}

if [ -n "${ANPR_SITE_PROFILE:-}" ]; then
  merge_profile "sites/${ANPR_SITE_PROFILE}.env"
  exit 0
fi

mapfile -t profiles < <(
  for f in sites/*.env; do
    [ -f "$f" ] || continue
    case "$f" in *.example) continue ;; esac
    basename "$f"
  done | sort
)

if [ "${#profiles[@]}" -eq 0 ]; then
  echo ""
  echo "  Inga site-profiler hittades."
  echo "  Kopiera t.ex. sites/falun.env.example till sites/falun.env"
  echo "  och fyll i RTSP-adress."
  echo ""
  if [ -f ".env" ]; then
    echo "  Fortsätter med befintlig .env"
    exit 0
  fi
  cp .env.example .env
  exit 0
fi

if [ "${#profiles[@]}" -eq 1 ]; then
  merge_profile "sites/${profiles[0]}"
  exit 0
fi

echo ""
echo "  Välj anläggning:"
echo ""
i=1
declare -a names
for f in "${profiles[@]}"; do
  name="${f%.env}"
  names+=("$name")
  echo "    $i) $name"
  i=$((i + 1))
done
echo ""
read -r -p "  Val [1-${#profiles[@]}]: " choice

if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#profiles[@]}" ]; then
  echo "Ogiltigt val"
  exit 1
fi

selected="${names[$((choice - 1))]}"
merge_profile "sites/${selected}.env"
