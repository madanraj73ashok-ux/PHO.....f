#!/usr/bin/env bash
# One-command local server deploy
set -e

PORT="${1:-8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================================="
echo " Deploying Local-First Phone Tracker Server"
echo " Host: http://localhost:${PORT}"
echo " Directory: ${SCRIPT_DIR}"
echo "=================================================="

exec python3 "${SCRIPT_DIR}/server.py" "${PORT}"
