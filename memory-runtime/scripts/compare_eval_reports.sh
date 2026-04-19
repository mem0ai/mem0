#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

BEFORE_PATH="${1:-${BEFORE:-}}"
AFTER_PATH="${2:-${AFTER:-}}"

if [[ -z "$BEFORE_PATH" || -z "$AFTER_PATH" ]]; then
  printf 'Usage: %s <before-report> <after-report>\n' "$0" >&2
  printf 'Or set BEFORE=/path/to/before AFTER=/path/to/after\n' >&2
  exit 1
fi

cd "$ROOT_DIR"
"$PYTHON_BIN" -m app.regression_compare --before "$BEFORE_PATH" --after "$AFTER_PATH"
