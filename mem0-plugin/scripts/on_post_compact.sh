#!/usr/bin/env bash
# Hook: PostCompact (matcher: manual|auto)
#
# Fires after context compaction completes. Injects a recovery prompt
# telling the agent to reload context from mem0.
#
# Input:  JSON on stdin with trigger, messages_retained, messages_removed
# Output: Context injected into Claude's post-compaction context (exit 0)

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

INPUT=$(cat)
TRIGGER=$(echo "$INPUT" | jq -r '.trigger // "auto"' 2>/dev/null || echo "auto")
RETAINED=$(echo "$INPUT" | jq -r '.messages_retained // "?"' 2>/dev/null || echo "?")
REMOVED=$(echo "$INPUT" | jq -r '.messages_removed // "?"' 2>/dev/null || echo "?")

# Telemetry (background)
python3 "$SCRIPT_DIR/telemetry.py" post_compact --trigger="$TRIGGER" --retained="$RETAINED" --removed="$REMOVED" 2>/dev/null &

if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

USER_ID="${MEM0_RESOLVED_USER_ID:-$USER}"
PROJECT_ID="${MEM0_PROJECT_ID:-unknown}"

cat <<EOF
## Mem0 Post-Compaction Recovery

Compaction complete ($TRIGGER). $REMOVED messages removed, $RETAINED retained.

You lost most conversation history. Recover context NOW:

1. \`search_memories(query="session state current task", filters={"AND": [{"user_id": "$USER_ID"}, {"app_id": "$PROJECT_ID"}, {"metadata": {"type": "session_state"}}]})\`
2. \`search_memories(query="recent decisions and learnings", filters={"AND": [{"user_id": "$USER_ID"}, {"app_id": "$PROJECT_ID"}, {"metadata": {"type": "decision"}}]})\`
3. \`search_memories(query="compact summary", filters={"AND": [{"user_id": "$USER_ID"}, {"app_id": "$PROJECT_ID"}, {"metadata": {"type": "compact_summary"}}]})\`

Run all 3 in parallel. Use results to resume work without asking user to repeat context.
EOF

exit 0
