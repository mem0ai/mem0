#!/usr/bin/env bash
# Hook: PreToolUse (matcher: Write|Edit)
#
# Blocks writes to MEMORY.md and auto-memory files, redirecting Claude
# to use the mem0 MCP add_memory tool instead.
#
# Input:  JSON on stdin with tool_name, tool_input
# Output: stderr message (exit 2 = block)
#
# Exit codes:
#   0 = allow the tool call
#   2 = block the tool call (stderr is shown to Claude as feedback)

set -euo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""' 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

case "$FILE_PATH" in
  */MEMORY.md|*/.claude/memory/*)
    echo "BLOCKED: Do not write to $FILE_PATH. Use the mem0 MCP \`add_memory\` tool instead to persist memories. This project uses mem0 for all memory storage." >&2
    exit 2
    ;;
  *)
    exit 0
    ;;
esac
