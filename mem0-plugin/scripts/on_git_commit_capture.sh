#!/usr/bin/env bash
# Hook: PreToolUse (matcher: Bash)
#
# Detects `git commit` commands and fires on_pre_commit.py in the background
# to capture staged changes as a mem0 memory. Never blocks the commit.
#
# Input:  JSON on stdin with tool_name, tool_input
# Output: none (always exit 0)

set -euo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")

if [ -z "$COMMAND" ]; then
  exit 0
fi

case "$COMMAND" in
  *"git commit"*|*"git merge"*|*"git rebase"*)
    ;;
  *)
    exit 0
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -x "$SCRIPT_DIR/on_pre_commit.py" ] && [ ! -f "$SCRIPT_DIR/on_pre_commit.py" ]; then
  exit 0
fi

API_KEY="${MEM0_API_KEY:-${CLAUDE_PLUGIN_OPTION_MEM0_API_KEY:-}}"
if [ -z "$API_KEY" ]; then
  exit 0
fi

git diff --cached --stat 2>/dev/null | python3 "$SCRIPT_DIR/on_pre_commit.py" &

exit 0
