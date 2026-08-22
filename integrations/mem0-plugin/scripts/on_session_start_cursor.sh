#!/usr/bin/env bash
# Hook: sessionStart (Cursor)
#
# Wraps on_session_start.sh and converts plain-text output to Cursor's
# expected JSON format: {"additional_context":"<text>"}

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Pin platform so the shared script's telemetry is attributed to cursor.
export MEM0_PLATFORM=cursor

# Never block Cursor's sessionStart on startup work: fast mode makes the
# shared script skip foreground network calls (memory count, activity
# timeline) and fully detach background jobs (auto-import, category setup,
# telemetry) so they cannot hold this hook's stdout open and delay or race
# the initial additional_context response.
export MEM0_FAST_SESSION_START=1

TEXT=$("$SCRIPT_DIR/on_session_start.sh" 2>/dev/null || echo "")

if [ -z "$TEXT" ]; then
  echo '{}'
  exit 0
fi

jq -cn --arg ctx "$TEXT" '{additional_context:$ctx}'
exit 0
