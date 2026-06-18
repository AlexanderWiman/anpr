#!/bin/bash
# Dubbelklicka för att installera ANPR (Mac)
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
  osascript -e 'display alert "Python saknas" message "Installera Python 3.11+ från python.org och försök igen."'
  exit 1
fi

python3 -m installer 2>/dev/null || python3 -m installer.cli
