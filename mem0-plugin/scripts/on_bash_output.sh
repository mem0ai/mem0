#!/usr/bin/env bash
# Hook: PostToolUse (matcher: Bash)
#
# Scans bash command output for stack traces and error patterns.
# When found, injects a search rubric telling the agent to check mem0
# for prior occurrences of the same error.
#
# This complements on_user_prompt.sh (which catches errors in the user's
# typed message). This hook catches errors in COMMAND OUTPUT — e.g.,
# when `npm test` or `python script.py` fails with a traceback.
#
# Input:  JSON on stdin with tool_name, tool_input, tool_output
# Output: Context injected into Claude's next response (exit 0)

set -uo pipefail

INPUT=$(cat)

TOOL_RESULT=$(echo "$INPUT" | jq -r '.tool_output // ""' 2>/dev/null || echo "")

# Skip short output (< 50 chars unlikely to contain a real stack trace)
if [ ${#TOOL_RESULT} -lt 50 ]; then
  exit 0
fi

# Skip if this is a git commit (handled by on_post_commit.sh)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
case "$COMMAND" in
  *"git commit"*|*"git merge"*|*"git rebase"*)
    exit 0
    ;;
esac

# Detect stack traces and error patterns in command output
HAS_ERROR=""
if echo "$TOOL_RESULT" | grep -qE '(Traceback \(most recent call last\)|panic: |FATAL:|error\[E[0-9]+\])'; then
  HAS_ERROR="true"
elif [ "$(echo "$TOOL_RESULT" | grep -cE '(Error:|Exception:)')" -ge 2 ]; then
  HAS_ERROR="true"
fi

if [ -z "$HAS_ERROR" ]; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

# Extract error class/message (first matching line)
ERROR_LINE=$(echo "$TOOL_RESULT" | grep -iE '(Error:|Exception:|panic:|FAIL:|fatal:)' | head -1 | sed 's/^[[:space:]]*//' | cut -c1-120)

# Extract file paths from stack trace frames
TRACE_FILES=$(echo "$TOOL_RESULT" | grep -oE '([a-zA-Z0-9_./-]+\.(py|ts|tsx|js|jsx|rs|go|rb|java|sh))(:[0-9]+)?' | head -5 | sort -u)

# Build file list for display
FILE_DISPLAY=""
if [ -n "$TRACE_FILES" ]; then
  FILE_DISPLAY=$(echo "$TRACE_FILES" | sed 's/^/  - /')
fi

USER_ID="$MEM0_RESOLVED_USER_ID"

cat <<EOF

## Error detected in command output

\`$COMMAND\` produced an error:
> $ERROR_LINE

EOF

if [ -n "$FILE_DISPLAY" ]; then
  cat <<EOF
**Files in stack trace:**
$FILE_DISPLAY

EOF
fi

cat <<EOF
Search mem0 for prior occurrences — this error may have been seen before:
- \`search_memories(query="$(echo "$ERROR_LINE" | cut -c1-60)", filters={"AND": [{"user_id": "$USER_ID"}, {"app_id": "$MEM0_PROJECT_ID"}, {"metadata": {"type": "anti_pattern"}}]})\`
- \`search_memories(query="$(echo "$ERROR_LINE" | cut -c1-60)", filters={"AND": [{"user_id": "$USER_ID"}, {"app_id": "$MEM0_PROJECT_ID"}, {"metadata": {"type": "bug_fix"}}]})\`
EOF

if [ -n "$TRACE_FILES" ]; then
  FIRST_FILE=$(echo "$TRACE_FILES" | head -1 | sed 's/:[0-9]*//')
  cat <<EOF
- \`search_memories(query="$FIRST_FILE", filters={"AND": [{"user_id": "$USER_ID"}, {"app_id": "$MEM0_PROJECT_ID"}]})\`
EOF
fi

cat <<EOF

If mem0 returns relevant context, use it to debug faster.
If you solve this, store the fix as an \`anti_pattern\` or \`bug_fix\` memory for next time.
EOF

# Telemetry
python3 "$SCRIPT_DIR/telemetry.py" bash_error --error_detected 2>/dev/null &

exit 0
