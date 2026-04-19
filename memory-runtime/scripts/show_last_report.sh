#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/.artifacts"

case "${1:-}" in
  smoke)
    REPORT_PATH="$REPORT_DIR/openclaw_pilot_smoke_report.json"
    ;;
  quality)
    REPORT_PATH="$REPORT_DIR/recall_quality_eval_report.json"
    ;;
  *)
    printf 'Usage: %s <smoke|quality>\n' "$0" >&2
    exit 1
    ;;
esac

if [[ ! -f "$REPORT_PATH" ]]; then
  printf 'Report not found: %s\n' "$REPORT_PATH" >&2
  exit 1
fi

printf 'Showing report: %s\n' "$REPORT_PATH"
if command -v jq >/dev/null 2>&1; then
  jq . "$REPORT_PATH"
else
  cat "$REPORT_PATH"
fi
