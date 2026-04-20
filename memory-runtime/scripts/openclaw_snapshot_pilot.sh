#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="$ROOT_DIR/.artifacts"
SNAPSHOT_ROOT="$ARTIFACT_DIR/pilot_snapshots"

RAW_NAME="${1:-}"
if [[ -z "$RAW_NAME" ]]; then
  RAW_NAME="$(python -m app.pilot_snapshots --default-name)"
fi

SNAPSHOT_NAME="$(python -m app.pilot_snapshots --sanitize "$RAW_NAME")"
SNAPSHOT_DIR="$SNAPSHOT_ROOT/$SNAPSHOT_NAME"
REPORT_DIR="$SNAPSHOT_DIR/reports"

mkdir -p "$REPORT_DIR"

cd "$ROOT_DIR"
docker compose up -d postgres memory-api >/dev/null

docker compose exec -T postgres pg_dump \
  -U postgres \
  -d memory_runtime \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges > "$SNAPSHOT_DIR/memory_runtime.sql"

for report in \
  openclaw_preflight_report.json \
  openclaw_pilot_smoke_report.json \
  openclaw_pilot_scenarios_report.json \
  recall_quality_eval_report.json
do
  if [[ -f "$ARTIFACT_DIR/$report" ]]; then
    cp "$ARTIFACT_DIR/$report" "$REPORT_DIR/$report"
  fi
done

docker compose exec -T memory-api python -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/v1/observability/stats').read().decode())" \
  > "$SNAPSHOT_DIR/observability_stats.json"

python -m app.pilot_snapshots \
  --write-manifest \
  --snapshot-dir "$SNAPSHOT_DIR" \
  --name "$SNAPSHOT_NAME" >/dev/null

printf 'Pilot snapshot saved: %s\n' "$SNAPSHOT_DIR"
