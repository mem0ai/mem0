#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

cd "$ROOT_DIR"
"$PYTHON_BIN" -m app.inspect_memory explain-recall "$@"
