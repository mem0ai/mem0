#!/usr/bin/env bash
# Hook: PostToolUse (matcher: Bash)
#
# Fires AFTER a Bash tool call completes. When a git commit/merge/rebase
# just succeeded, surfaces 1-3 relevant memories from the changed files
# and prompts Claude to ask the user if this change should be stored as
# a learning.
#
# Input:  JSON on stdin with tool_name, tool_input, tool_response
# Output: Context injected into Claude's next response (exit 0)
#
# This implements Spec #28 — interactive pre-commit memory check.

set -uo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Only trigger on git commit/merge/rebase commands
case "$COMMAND" in
  *"git commit"*|*"git merge"*|*"git rebase"*)
    ;;
  *)
    exit 0
    ;;
esac

# Check if the command actually succeeded (look for commit hash in output)
TOOL_RESULT=$(echo "$INPUT" | jq -r '.tool_response // ""' 2>/dev/null || echo "")
if echo "$TOOL_RESULT" | grep -qiE '(error|fatal|abort|nothing to commit|no changes)'; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

# No API key — skip interactive prompt
if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

# C5: commit prompts default OFF — only prompt if explicitly enabled in mem0.md
MEM0_CWD=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
COMMIT_PROMPTS=$(python3 "$SCRIPT_DIR/parse_mem0_config.py" --key settings.commit_prompts "$MEM0_CWD" 2>/dev/null || echo "")
if [ "$COMMIT_PROMPTS" != "true" ]; then
  exit 0
fi

# Extract changed files from commit
CHANGED_FILES=$(git -C "$MEM0_CWD" diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null | head -10 || echo "")
if [ -z "$CHANGED_FILES" ]; then
  exit 0
fi

# Get the commit message
COMMIT_MSG=$(git -C "$MEM0_CWD" log -1 --format='%s' HEAD 2>/dev/null || echo "")

# Build file list for display
FILE_LIST=$(echo "$CHANGED_FILES" | sed 's/^/  - /' | head -5)
FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')

CTX="Commit captured: ${COMMIT_MSG}\nFiles changed (${FILE_COUNT}):\n${FILE_LIST}\n\nCommit learnings (decision, task_learning, anti_pattern, convention) are stored via add_memory with user_id=${MEM0_RESOLVED_USER_ID}, app_id=${MEM0_PROJECT_ID}, branch=${MEM0_BRANCH}."

jq -cn --arg ctx "$CTX" '{
  hookSpecificOutput: {
    hookEventName: "PostToolUse",
    additionalContext: $ctx
  }
}' 2>/dev/null || true

# Telemetry
python3 "$SCRIPT_DIR/telemetry.py" post_commit --files_count="$FILE_COUNT" 2>/dev/null &

exit 0
