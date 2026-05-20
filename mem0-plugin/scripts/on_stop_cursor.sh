#!/usr/bin/env bash
# Hook: Stop (Cursor)
#
# Fires when Cursor agent completes a turn. Wraps the same logic as
# on_stop.sh but outputs JSON (Cursor expects {"followup_message":"..."}).
#
# Input:  JSON on stdin with status, loop_count, conversation_id, etc.
# Output: JSON on stdout: {"followup_message":"<reminder text>"}

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

INPUT=$(cat)

# Session-end report (best-effort)
REPORT=$(python3 "$SCRIPT_DIR/session_stats.py" report 2>/dev/null || echo "")
REPORT_BLOCK=""
if [ -n "$REPORT" ]; then
  REPORT_BLOCK="---\nmem0 $REPORT\n---\n\n"
  mkdir -p "$HOME/.mem0" 2>/dev/null || true
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | $REPORT" >> "$HOME/.mem0/session-log.md" 2>/dev/null || true
fi

MESSAGE=$(cat <<EOF
${REPORT_BLOCK}Before finishing, check if there are important learnings from this interaction that should be persisted using the mem0 \`add_memory\` tool:

1. Were any significant decisions made? -> Store with metadata \`{"type": "decision"}\`
2. Were any new patterns or strategies discovered? -> Store with metadata \`{"type": "task_learning"}\`
3. Did any approach fail? -> Store with metadata \`{"type": "anti_pattern"}\`
4. Did you learn anything about the user's preferences? -> Store with metadata \`{"type": "user_preference"}\`
5. Were there environment/setup discoveries? -> Store with metadata \`{"type": "environmental"}\`

Always include \`"project_id"\` in the metadata of any memory you store.

If nothing notable happened, it's fine to skip. Only store genuinely useful learnings.
EOF
)

jq -cn --arg msg "$MESSAGE" '{followup_message:$msg}'

# Capture transcript state in the background via Mem0 REST API
echo "$INPUT" | python3 "$SCRIPT_DIR/on_pre_compact.py" --source=session-end 2>/dev/null &

exit 0
