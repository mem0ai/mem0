#!/usr/bin/env bash
# Hook: preCompact (Cursor)
#
# Wraps on_pre_compact.sh and converts plain-text output to Cursor's
# expected JSON format: {"user_message":"<text>"}

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Pin platform so the shared script's telemetry is attributed to cursor.
export MEM0_PLATFORM=cursor

TEXT=$("$SCRIPT_DIR/on_pre_compact.sh" 2>/dev/null || echo "")

if [ -z "$TEXT" ]; then
  echo '{}'
  exit 0
fi

jq -cn --arg msg "$TEXT" '{user_message:$msg}'
exit 0
