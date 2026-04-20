#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/.artifacts"
REPORT_PATH="$REPORT_DIR/openclaw_negative_pilot_scenarios_report.json"
TMP_REPORT_PATH="$REPORT_PATH.tmp"
PYTHON_BIN="${PYTHON:-python3}"
RUN_NAME="manual-$(date +%Y%m%d-%H%M%S)"

mkdir -p "$REPORT_DIR"

cd "$ROOT_DIR"
"$PYTHON_BIN" -m app.pilot_negative_scenarios --artifact-run-name "$RUN_NAME" "$@" > "$TMP_REPORT_PATH"
mv "$TMP_REPORT_PATH" "$REPORT_PATH"

printf 'OpenClaw negative pilot scenarios report saved to %s\n' "$REPORT_PATH"
if command -v jq >/dev/null 2>&1; then
  jq . "$REPORT_PATH"
else
  cat "$REPORT_PATH"
fi
