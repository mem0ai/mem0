#!/usr/bin/env bash
# Hook: sessionStart (Cursor)
#
# Wraps on_session_start.sh and converts plain-text output to Cursor's
# expected JSON format: {"additional_context":"<text>"}

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Pin platform so the shared script's telemetry is attributed to cursor.
export MEM0_PLATFORM=cursor

TEXT=$("$SCRIPT_DIR/on_session_start.sh" 2>/dev/null || echo "")

if [ -z "$TEXT" ]; then
  echo '{}'
  exit 0
fi

jq -cn --arg ctx "$TEXT" '{additional_context:$ctx}'
exit 0
