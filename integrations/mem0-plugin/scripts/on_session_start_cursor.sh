#!/usr/bin/env bash
# Hook: sessionStart (Cursor)
#
# Wraps on_session_start.sh and converts plain-text output to Cursor's
# expected JSON format: {"additional_context":"<text>"}

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Pin platform so the shared script's telemetry is attributed to cursor.
export MEM0_PLATFORM=cursor
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

TEXT=$("$SCRIPT_DIR/on_session_start.sh" 2>/dev/null || echo "")

jq -cn \
  --arg ctx "$TEXT" \
  --arg user_id "${MEM0_RESOLVED_USER_ID:-${USER:-default}}" \
  --arg project_id "${MEM0_PROJECT_ID:-unknown}" \
  --arg branch "${MEM0_BRANCH:-unknown}" \
  --arg api_base "${MEM0_API_BASE:-}" \
  '{
    additional_context: $ctx,
    env: ({
      MEM0_RESOLVED_USER_ID: $user_id,
      MEM0_PROJECT_ID: $project_id,
      MEM0_BRANCH: $branch
    } + (if $api_base == "" then {} else {MEM0_API_BASE: $api_base} end))
  }'
exit 0
