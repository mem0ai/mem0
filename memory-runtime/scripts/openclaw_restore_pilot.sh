#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="$ROOT_DIR/.artifacts"
SNAPSHOT_ROOT="$ARTIFACT_DIR/pilot_snapshots"
SNAPSHOT_NAME="${1:-}"

if [[ -z "$SNAPSHOT_NAME" ]]; then
  printf 'Usage: %s <snapshot-name>\n' "$0" >&2
  exit 1
fi

SNAPSHOT_DIR="$SNAPSHOT_ROOT/$SNAPSHOT_NAME"
SQL_DUMP="$SNAPSHOT_DIR/memory_runtime.sql"
REPORT_DIR="$SNAPSHOT_DIR/reports"

if [[ ! -f "$SQL_DUMP" ]]; then
  printf 'Snapshot dump not found: %s\n' "$SQL_DUMP" >&2
  exit 1
fi

cd "$ROOT_DIR"
docker compose up -d postgres redis >/dev/null

until docker compose exec -T postgres pg_isready -U postgres -d postgres >/dev/null 2>&1; do
  sleep 1
done

docker compose exec -T postgres dropdb -U postgres --if-exists memory_runtime
docker compose exec -T postgres createdb -U postgres memory_runtime
docker compose exec -T postgres psql -U postgres -d memory_runtime < "$SQL_DUMP"

if [[ -d "$REPORT_DIR" ]]; then
  mkdir -p "$ARTIFACT_DIR"
  find "$REPORT_DIR" -maxdepth 1 -type f -name '*.json' -exec cp {} "$ARTIFACT_DIR/" \;
fi

if [[ -f "$SNAPSHOT_DIR/observability_stats.json" ]]; then
  cp "$SNAPSHOT_DIR/observability_stats.json" "$ARTIFACT_DIR/restored_observability_stats.json"
fi

docker compose up -d memory-api memory-worker >/dev/null

printf 'Pilot snapshot restored: %s\n' "$SNAPSHOT_DIR"
