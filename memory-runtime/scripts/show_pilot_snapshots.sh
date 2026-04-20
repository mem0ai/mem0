#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT_ROOT="$ROOT_DIR/.artifacts/pilot_snapshots"

if [[ ! -d "$SNAPSHOT_ROOT" ]]; then
  printf 'No pilot snapshots found.\n'
  exit 0
fi

find "$SNAPSHOT_ROOT" -mindepth 1 -maxdepth 1 -type d | sort | while read -r dir; do
  printf '%s\n' "$(basename "$dir")"
  if [[ -f "$dir/manifest.json" ]]; then
    if command -v jq >/dev/null 2>&1; then
      jq '{snapshot_name, created_at, reports, has_observability_snapshot}' "$dir/manifest.json"
    else
      cat "$dir/manifest.json"
    fi
  fi
done
