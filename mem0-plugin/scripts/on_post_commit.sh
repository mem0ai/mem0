#!/usr/bin/env bash
# Hook: PostToolUse (matcher: Bash)
#
# Fires AFTER a Bash tool call completes. When a git commit/merge/rebase
# just succeeded, surfaces 1-3 relevant memories from the changed files
# and prompts Claude to ask the user if this change should be stored as
# a learning.
#
# Input:  JSON on stdin with tool_name, tool_input, tool_output
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
TOOL_RESULT=$(echo "$INPUT" | jq -r '.tool_output // ""' 2>/dev/null || echo "")
if echo "$TOOL_RESULT" | grep -qiE '(error|fatal|abort|nothing to commit|no changes)'; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

# No API key — skip interactive prompt
if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

# Extract changed files from commit
CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | head -10 || echo "")
if [ -z "$CHANGED_FILES" ]; then
  exit 0
fi

# Get the commit message
COMMIT_MSG=$(git log -1 --format='%s' HEAD 2>/dev/null || echo "")

# Build file list for display
FILE_LIST=$(echo "$CHANGED_FILES" | sed 's/^/  - /' | head -5)
FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')

cat <<EOF

## Commit captured — save as memory?

**Commit:** $COMMIT_MSG
**Files changed ($FILE_COUNT):**
$FILE_LIST

This commit may contain learnings worth preserving. Ask the user:

> **Save this change as a memory?** I can store it as one of:
> - \`decision\` — if an architectural or design choice was made
> - \`task_learning\` — if a strategy or approach worked well
> - \`anti_pattern\` — if this fixes a bug or avoids a known pitfall
> - \`convention\` — if this establishes a new pattern
>
> Type the category, or **skip** to move on.

If the user provides a category (or says yes/sure/go ahead):
1. Summarize the commit: what changed and why (from the diff + commit message)
2. Call \`add_memory\` with:
   - \`messages=[{"role": "user", "content": "<your summary>"}]\`
   - \`user_id="$MEM0_RESOLVED_USER_ID"\`
   - \`app_id="$MEM0_PROJECT_ID"\`
   - \`metadata={"type": "<chosen_category>", "branch": "$MEM0_BRANCH", "confidence": 0.8, "files": [<changed files>], "source": "post-commit"}\`
   - \`infer=False\`

If the user says skip/no/nothing: proceed normally. Do NOT ask again for the same commit.
EOF

# Telemetry
python3 "$SCRIPT_DIR/telemetry.py" post_commit --files_count="$FILE_COUNT" 2>/dev/null &

exit 0
