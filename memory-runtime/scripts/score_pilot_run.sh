#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

if [[ -z "${1:-}" ]]; then
  printf 'Usage: %s <scorecard-json>\n' "$0" >&2
  exit 1
fi

cd "$ROOT_DIR"
"$PYTHON_BIN" -m app.pilot_scorecard --input "$1"
