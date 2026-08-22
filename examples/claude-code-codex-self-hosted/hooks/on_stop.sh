#!/usr/bin/env bash
# Hook: Stop
#
# Fires when the session ends. Persists the final exchanges so nothing is
# lost between sessions. Complements on_pre_compact (which covers the
# mid-session compaction point).
#
# Input:  JSON on stdin (session_id, transcript_path, cwd)
# Output: none (side effect: memory persistence)
#
# Must never block session end: any failure exits 0 silently.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=mem0_env.sh
. "$SCRIPT_DIR/mem0_env.sh" 2>/dev/null || exit 0

if ! mem0_ready; then
  exit 0
fi

INPUT=$(cat)
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null || echo "")

if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  exit 0
fi

TAIL=$(tail -c 12000 "$TRANSCRIPT_PATH" 2>/dev/null || echo "")

if [ -z "$TAIL" ]; then
  exit 0
fi

mem0_add "Session transcript excerpt from session end (extract durable facts, decisions, and preferences): ${TAIL}" \
  "{\"source\": \"session_end\"}"

exit 0
