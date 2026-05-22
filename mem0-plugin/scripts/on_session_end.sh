#!/usr/bin/env bash
# Hook: SessionEnd
#
# Fires when session actually terminates (after Stop).
# Last-chance capture: if on_stop.sh background REST call didn't complete,
# this fires a synchronous capture attempt.
#
# Input:  JSON on stdin with session_id, transcript_path, cwd, reason
# Output: ignored (session is ending)

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

INPUT=$(cat)
REASON=$(echo "$INPUT" | jq -r '.reason // "other"' 2>/dev/null || echo "other")
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""' 2>/dev/null || echo "")

# Telemetry (fire-and-forget — session dying, best-effort)
python3 "$SCRIPT_DIR/telemetry.py" session_end --reason="$REASON" 2>/dev/null &

# Check if on_stop.sh already captured this session (avoid duplicates)
CAPTURE_MARKER="$HOME/.mem0/.captured_${SESSION_ID}"
if [ -n "$SESSION_ID" ] && [ -f "$CAPTURE_MARKER" ]; then
  exit 0
fi

# Last-chance transcript capture (synchronous — session is ending anyway)
if [ -n "${MEM0_API_KEY:-}" ]; then
  echo "$INPUT" | python3 "$SCRIPT_DIR/on_pre_compact.py" --source=session-end 2>/dev/null || true
  # Mark as captured to prevent duplicate if Stop also ran
  if [ -n "$SESSION_ID" ]; then
    mkdir -p "$HOME/.mem0" 2>/dev/null || true
    touch "$CAPTURE_MARKER" 2>/dev/null || true
    # Clean up old markers (> 7 days)
    find "$HOME/.mem0" -name ".captured_*" -mtime +7 -delete 2>/dev/null || true
  fi
fi

exit 0
