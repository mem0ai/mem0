#!/usr/bin/env bash
# Hook: PostToolUse — track mem0 MCP tool usage for session stats
#
# Fires after any tool call. We only care about mem0 MCP tools:
#   mcp__mem0__add_memory     → record an add
#   mcp__mem0__search_memories → record a search
#
# Input:  JSON on stdin with tool_name, tool_input, tool_response
# Output: none (exit 0, non-blocking)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")

case "$TOOL_NAME" in
  *__add_memory)
    CATEGORY=$(echo "$INPUT" | jq -r '.tool_input.metadata.type // .tool_input.metadata.category // ""' 2>/dev/null || echo "")
    python3 "$SCRIPT_DIR/session_stats.py" add "$CATEGORY" 2>/dev/null || true
    python3 "$SCRIPT_DIR/telemetry.py" tool_use --tool=add_memory 2>/dev/null &
    ;;
  *__search_memories|*__get_memories)
    python3 "$SCRIPT_DIR/session_stats.py" search 2>/dev/null || true
    python3 "$SCRIPT_DIR/telemetry.py" tool_use --tool=search_memories 2>/dev/null &
    ;;
  *__delete_memory)
    python3 "$SCRIPT_DIR/telemetry.py" tool_use --tool=delete_memory 2>/dev/null &
    ;;
  *__update_memory)
    python3 "$SCRIPT_DIR/telemetry.py" tool_use --tool=update_memory 2>/dev/null &
    ;;
esac

exit 0
