#!/bin/bash
# Installerar Python och ffmpeg om de saknas (Mac).
set -euo pipefail

log() { echo "[prerequisites] $*"; }

if command -v brew >/dev/null 2>&1; then
  if ! command -v ffmpeg >/dev/null 2>&1; then
    log "Installerar ffmpeg via Homebrew..."
    brew install ffmpeg
  else
    log "ffmpeg — OK"
  fi

  if ! python3 -c 'import sys; assert sys.version_info >= (3, 11)' 2>/dev/null \
    && ! /opt/homebrew/bin/python3 -c 'import sys; assert sys.version_info >= (3, 11)' 2>/dev/null \
    && ! /usr/local/bin/python3 -c 'import sys; assert sys.version_info >= (3, 11)' 2>/dev/null; then
    log "Installerar Python 3.12 via Homebrew..."
    brew install python@3.12
  else
    log "Python — OK"
  fi
else
  log "Homebrew saknas — installera Python från https://www.python.org/downloads/"
  log "FFmpeg: installera Homebrew (https://brew.sh) eller be IT om hjälp"
fi

if command -v ffmpeg >/dev/null 2>&1; then
  log "ffmpeg — OK"
else
  log "VARNING: ffmpeg saknas fortfarande"
fi

if python3 -c 'import sys; assert sys.version_info >= (3, 11)' 2>/dev/null; then
  log "Python — OK"
else
  log "VARNING: Python 3.11+ saknas fortfarande"
fi
