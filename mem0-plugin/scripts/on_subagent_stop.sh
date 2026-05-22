#!/usr/bin/env bash
# Hook: SubagentStop
#
# Fires when a subagent finishes. Injects a reminder to capture any
# learnings the subagent produced that the parent agent should store.
#
# Input:  JSON on stdin with agent_type, result_summary
# Output: Context injected into parent agent's context (exit 0)

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

INPUT=$(cat)
AGENT_TYPE=$(echo "$INPUT" | jq -r '.agent_type // ""' 2>/dev/null || echo "")
RESULT_SUMMARY=$(echo "$INPUT" | jq -r '.result_summary // ""' 2>/dev/null || echo "")

# Skip short/empty results — nothing worth capturing
if [ ${#RESULT_SUMMARY} -lt 50 ]; then
  exit 0
fi

# Skip explorer/plan agents — read-only, rarely produce storable learnings
case "$AGENT_TYPE" in
  Explore|Plan)
    exit 0
    ;;
esac

if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

cat <<EOF

## Subagent completed: $AGENT_TYPE

Review the subagent result for learnings worth persisting to mem0.
If the subagent discovered something reusable (a fix, pattern, decision, or anti-pattern),
store it via \`add_memory\` with appropriate metadata type.

Only store if genuinely valuable — skip trivial subagent results.
EOF

exit 0
