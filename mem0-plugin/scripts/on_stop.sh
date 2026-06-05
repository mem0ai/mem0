#!/usr/bin/env bash
# Hook: Stop
#
# Captures a structured session summary when a Claude Code session ends.
# Parses the transcript, extracts the last assistant message and files
# touched, then stores via mem0 API with infer=True for AI extraction.
#
# Guards:
#   - Skips subagent sessions (agent_id present)
#   - Skips if no API key
#   - Skips if no transcript_path
#   - Dedup via marker file
#
# Input:  JSON on stdin with transcript_path, session_id, agent_id, cwd
# Output: Nothing to stdout (background capture). Always exits 0.

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

INPUT=$(cat)

# Guard: skip subagent sessions
AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // ""' 2>/dev/null || echo "")
if [ -n "$AGENT_ID" ]; then
  exit 0
fi

# Resolve identity if needed
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

if [ "${MEM0_AUTO_SAVE:-true}" = "false" ]; then
  exit 0
fi

TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""' 2>/dev/null || echo "")
if [ -z "$TRANSCRIPT_PATH" ]; then
  exit 0
fi

# Run capture in the background — fires every turn now, so avoid blocking
echo "$INPUT" | python3 "$SCRIPT_DIR/capture_session_summary.py" 2>/dev/null &

# Telemetry
python3 "$SCRIPT_DIR/telemetry.py" session_stop 2>/dev/null &

exit 0
