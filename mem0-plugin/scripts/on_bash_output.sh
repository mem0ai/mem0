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

# Extract query (first 80 chars of error line)
ERROR_QUERY=$(echo "$ERROR_LINE" | cut -c1-80)

# Pre-fetch memories: anti_pattern and bug_fix searches (requires API key)
RESULTS=""
if [ -n "${MEM0_API_KEY:-}" ]; then
  RESULTS=$(PYTHONPATH="$SCRIPT_DIR" MEM0_SEARCH_QUERY="$ERROR_QUERY" MEM0_SEARCH_USER="$USER_ID" \
    MEM0_API_KEY="${MEM0_API_KEY}" MEM0_PROJECT_ID="${MEM0_PROJECT_ID:-unknown}" \
    python3 -c "
import os, sys
sys.path.insert(0, os.environ.get('PYTHONPATH', '.'))
from _search import search_memories, format_results_for_context

api_key = os.environ.get('MEM0_API_KEY', '')
user_id = os.environ.get('MEM0_SEARCH_USER', 'default')
project_id = os.environ.get('MEM0_PROJECT_ID', 'unknown')
query = os.environ.get('MEM0_SEARCH_QUERY', '')

r1 = search_memories(api_key, user_id, project_id, query, metadata_type='anti_pattern', top_k=3)
r2 = search_memories(api_key, user_id, project_id, query, metadata_type='bug_fix', top_k=3)

# Deduplicate by ID
seen = set()
combined = []
for m in r1 + r2:
    mid = m.get('id', '')
    if mid not in seen:
        seen.add(mid)
        combined.append(m)

print(format_results_for_context(combined, heading='Prior error memories'), end='')
" 2>/dev/null || echo "")
fi

# Output error header
printf '\n## Error detected in command output\n\n'
printf '`%s` produced an error:\n> %s\n\n' "$COMMAND" "$ERROR_LINE"

if [ -n "$FILE_DISPLAY" ]; then
  printf '**Files in stack trace:**\n%s\n\n' "$FILE_DISPLAY"
fi

# Output search results or fallback
if [ -n "$RESULTS" ]; then
  printf '%s\n' "$RESULTS"
else
  printf 'No prior memories found for this error.\n\n'
fi

printf 'If you solve this, store the fix as an `anti_pattern` or `bug_fix` memory for next time.\n'

# Telemetry
python3 "$SCRIPT_DIR/telemetry.py" bash_error --error_detected 2>/dev/null &

exit 0
