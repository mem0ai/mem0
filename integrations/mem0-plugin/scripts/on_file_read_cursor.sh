#!/usr/bin/env bash
# Hook: preToolUse (matcher: Read) — Cursor variant
#
# Same as on_file_read.sh but uses CURSOR_PLUGIN_ROOT for path resolution
# and sources Cursor-specific identity.

set -uo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null || echo "")
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

if [ -z "${MEM0_API_KEY:-}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  . "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true
fi
if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CWD=$(echo "$INPUT" | jq -r '.cwd // "."' 2>/dev/null || echo ".")

TIMELINE=$(python3 "$SCRIPT_DIR/file_context.py" "$FILE_PATH" "$CWD" 2>/dev/null || echo "")

if [ -z "$TIMELINE" ]; then
  exit 0
fi

jq -cn --arg ctx "$TIMELINE" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: $ctx,
    permissionDecision: "allow"
  }
}' 2>/dev/null || true

exit 0
