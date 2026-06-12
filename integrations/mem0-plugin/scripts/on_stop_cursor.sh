#!/usr/bin/env bash
# Hook: stop — Cursor variant
#
# Same as on_stop.sh but uses CURSOR_PLUGIN_ROOT and Cursor-specific
# identity resolution.

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

INPUT=$(cat)

AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // ""' 2>/dev/null || echo "")
if [ -n "$AGENT_ID" ]; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""' 2>/dev/null || echo "")
if [ -z "$TRANSCRIPT_PATH" ]; then
  exit 0
fi

echo "$INPUT" | python3 "$SCRIPT_DIR/capture_session_summary.py" 2>/dev/null || true

python3 "$SCRIPT_DIR/telemetry.py" session_stop 2>/dev/null &

exit 0
