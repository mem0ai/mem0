#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/.artifacts"
REPORT_PATH="$REPORT_DIR/openclaw_preflight_report.json"
TMP_REPORT_PATH="$REPORT_PATH.tmp"
PYTHON_BIN="${PYTHON:-python3}"

mkdir -p "$REPORT_DIR"

cd "$ROOT_DIR"
"$PYTHON_BIN" -m app.preflight "$@" > "$TMP_REPORT_PATH"
mv "$TMP_REPORT_PATH" "$REPORT_PATH"

printf 'OpenClaw preflight report saved to %s\n' "$REPORT_PATH"
if command -v jq >/dev/null 2>&1; then
  jq . "$REPORT_PATH"
else
  cat "$REPORT_PATH"
fi
