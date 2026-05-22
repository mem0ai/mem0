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

# Print session-end report (last chance — Stop hook output may not render on /exit)
REPORT=$(python3 "$SCRIPT_DIR/session_stats.py" report 2>/dev/null || echo "")
if [ -n "$REPORT" ] && [ "$REPORT" != "Session: no memory operations." ]; then
  echo ""
  echo "---"
  echo "mem0 $REPORT"
  echo "---"

  # Append to persistent session log
  mkdir -p "$HOME/.mem0" 2>/dev/null || true
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | $REPORT" >> "$HOME/.mem0/session-log.md" 2>/dev/null || true
fi

# Telemetry (fire-and-forget — session dying, best-effort)
python3 "$SCRIPT_DIR/telemetry.py" session_end --reason="$REASON" 2>/dev/null &

# Clean up old capture markers (> 7 days)
find "$HOME/.mem0" -name ".captured_*" -mtime +7 -delete 2>/dev/null || true

exit 0
