#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/.artifacts"

cd "$ROOT_DIR"
docker compose down -v --remove-orphans || true

rm -f "$REPORT_DIR/openclaw_pilot_smoke_report.json"
rm -f "$REPORT_DIR/recall_quality_eval_report.json"
rm -f "$ROOT_DIR/memory_runtime.db"
rm -f /tmp/memory_runtime_worker_heartbeat

printf 'Pilot environment reset complete.\n'
