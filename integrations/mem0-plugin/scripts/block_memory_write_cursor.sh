#!/usr/bin/env bash
# Hook: preToolUse (Cursor) — blocks writes to MEMORY.md
#
# Cursor variant of block_memory_write.sh. Returns JSON:
# {"permission":"deny","agent_message":"..."} on block,
# {"permission":"allow"} on pass.

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""' 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
  jq -cn '{permission:"allow"}'
  exit 0
fi

case "$FILE_PATH" in
  */MEMORY.md|*/.claude/memory/*|*/.cursor/memory/*)
    jq -cn --arg msg "Do not write to $FILE_PATH. Use the mem0 MCP add_memory tool instead to persist memories." \
      '{permission:"deny", agent_message:$msg}'
    exit 0
    ;;
  *)
    jq -cn '{permission:"allow"}'
    exit 0
    ;;
esac
