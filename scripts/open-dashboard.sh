#!/usr/bin/env bash
open "http://localhost:${HEALTH_PORT:-8080}" 2>/dev/null || xdg-open "http://localhost:${HEALTH_PORT:-8080}" 2>/dev/null || echo "Open http://localhost:${HEALTH_PORT:-8080} in your browser"
