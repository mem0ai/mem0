#!/usr/bin/env bash
# Hook: postToolUse (Cursor) — track mem0 MCP tool usage for session stats
#
# Wraps on_post_tool_use.sh. Cursor expects JSON output but PostToolUse
# has no meaningful return value, so we output {} after tracking.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Run the shared tracker (output is ignored)
"$SCRIPT_DIR/on_post_tool_use.sh" 2>/dev/null || true

echo '{}'
exit 0
