#!/usr/bin/env bash
# Hook: Stop
#
# Fires when Claude finishes responding.
# Reminds Claude to store any unsaved learnings, then spawns a background
# process to capture transcript state via the Mem0 REST API directly.
#
# Input:  JSON on stdin with stop_hook_active, transcript_path, cwd
# Output: Text that becomes Claude's context (exit 0), or nothing
#
# IMPORTANT: Check stop_hook_active to avoid infinite loops.

# Intentionally omit -e so the reminder always emits even if session_stats fails.
set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

INPUT=$(cat)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")

if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

# Telemetry: fire before report() deletes stats file
_TELEM_CAT=$(python3 "$SCRIPT_DIR/session_stats.py" peek 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('categories',[])))" 2>/dev/null || echo "0")
python3 "$SCRIPT_DIR/telemetry.py" stop --categories_count="$_TELEM_CAT" 2>/dev/null &

# Print session-end report
REPORT=$(python3 "$SCRIPT_DIR/session_stats.py" report 2>/dev/null || echo "")
if [ -n "$REPORT" ]; then
  echo ""
  echo "---"
  echo "**mem0 $REPORT**"
  echo "---"
  echo ""
fi

# Append to persistent session log
if [ -n "$REPORT" ]; then
  mkdir -p "$HOME/.mem0" 2>/dev/null || true
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | $REPORT" >> "$HOME/.mem0/session-log.md" 2>/dev/null || true
fi

cat <<'EOF'
Store 0-2 durable facts from this turn via `add_memory` — only decisions, anti-patterns, or conventions that would help a future agent. Skip if nothing new was learned.
EOF

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""' 2>/dev/null || echo "")

exit 0
