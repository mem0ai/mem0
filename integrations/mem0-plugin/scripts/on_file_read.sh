#!/usr/bin/env bash
# Hook: PreToolUse (matcher: Read)
#
# Injects prior work context before Claude reads a file. Searches mem0
# for memories referencing the file path and returns a compact timeline.
#
# Modeled after claude-mem's file-context handler, adapted for mem0 cloud API.
#
# Input:  JSON on stdin with tool_name, tool_input (file_path), cwd
# Output: JSON with hookSpecificOutput.additionalContext + permissionDecision
#
# Must never block the Read — silent exit on any failure.

set -uo pipefail

INPUT=$(cat)

# Extract file path from tool_input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null || echo "")
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Resolve API key (covers Desktop app users who set it in shell profile)
if [ -z "${MEM0_API_KEY:-}" ]; then
  . "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true
fi
if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi
CWD=$(echo "$INPUT" | jq -r '.cwd // "."' 2>/dev/null || echo ".")

# Call the Python worker — it handles gating (file size, existence)
TIMELINE=$(python3 "$SCRIPT_DIR/file_context.py" "$FILE_PATH" "$CWD" 2>/dev/null || echo "")

if [ -z "$TIMELINE" ]; then
  exit 0
fi

# Return context injection with permissionDecision: allow
jq -cn --arg ctx "$TIMELINE" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: $ctx,
    permissionDecision: "allow"
  }
}' 2>/dev/null || true

exit 0
