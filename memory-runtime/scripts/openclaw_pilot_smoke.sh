#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/.artifacts"
REPORT_PATH="$REPORT_DIR/openclaw_pilot_smoke_report.json"
RUN_NAME="manual-$(date +%Y%m%d-%H%M%S)"

mkdir -p "$REPORT_DIR"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

cd "$ROOT_DIR"
docker compose up -d --build

for _ in $(seq 1 30); do
  if docker compose exec -T memory-api python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8080/healthz')" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

docker compose exec -T memory-api python -m app.pilot_smoke --base-url http://127.0.0.1:8080 --artifact-run-name "$RUN_NAME" > "$REPORT_PATH"

jq -e '
  (.recall_prior_decisions | map(contains("dedicated memory worker")) | any) and
  (.session_search_results | map(contains("acceptance checklist")) | any) and
  (.jobs_by_status.pending == 0) and
  (.jobs_by_status.completed >= 2)
' "$REPORT_PATH" >/dev/null

printf 'OpenClaw pilot smoke passed. Report: %s\n' "$REPORT_PATH"
cat "$REPORT_PATH"
