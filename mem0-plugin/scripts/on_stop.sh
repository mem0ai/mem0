#!/usr/bin/env bash
# Hook: Stop (Claude Code)
#
# Fires when Claude finishes responding. If meaningful work happened and
# no memories were stored, blocks stop so Claude can call MCP add_memory.
# REST API capture runs in background as fallback.
#
# Input:  JSON on stdin with session_id, transcript_path, cwd, response_text
# Output: JSON { decision: "block", reason: "..." } or exit 0

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_identity.sh
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

INPUT=$(cat)

# Telemetry
_TELEM_CAT=$(python3 "$SCRIPT_DIR/session_stats.py" peek 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('categories',[])))" 2>/dev/null || echo "0")
python3 "$SCRIPT_DIR/telemetry.py" stop --categories_count="$_TELEM_CAT" 2>/dev/null &

# Check if meaningful work happened
CHECK_RESULT=$(echo "$INPUT" | python3 "$SCRIPT_DIR/stop_hook_check.py" 2>/dev/null || echo '{"should_block":false}')
_SHOULD_CAPTURE=$(echo "$CHECK_RESULT" | jq -r '.should_block // false' 2>/dev/null || echo "false")

if [ "$_SHOULD_CAPTURE" != "true" ]; then
  exit 0
fi

# Log session report
REPORT=$(python3 "$SCRIPT_DIR/session_stats.py" report 2>/dev/null || echo "")
if [ -n "$REPORT" ]; then
  mkdir -p "$HOME/.mem0" 2>/dev/null || true
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | $REPORT" >> "$HOME/.mem0/session-log.md" 2>/dev/null || true
fi

# Background REST API capture (fallback)
_TMP="/tmp/mem0_stop_input_$$.json"
printf '%s' "$INPUT" > "$_TMP" 2>/dev/null
(python3 "$SCRIPT_DIR/on_pre_compact.py" --source=session-end < "$_TMP" 2>/dev/null; rm -f "$_TMP") &

# Check if agent already stored memories this session
_STATS_FILE="/tmp/mem0_session_stats_${USER:-default}.json"
_MEM_COUNT=0
if [ -f "$_STATS_FILE" ]; then
  _MEM_COUNT=$(python3 -c "import json; d=json.load(open('$_STATS_FILE')); print(d.get('adds',0))" 2>/dev/null || echo "0")
fi
if [ "${_MEM_COUNT:-0}" -gt 0 ] 2>/dev/null; then
  exit 0
fi

# One-shot guard: only block once per session
_SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""' 2>/dev/null || echo "")
_BLOCK_FLAG="/tmp/mem0_stop_blocked_${_SESSION_ID:-$$}"
if [ -f "$_BLOCK_FLAG" ]; then
  exit 0
fi
touch "$_BLOCK_FLAG" 2>/dev/null || true

# No API key — can't use MCP tools
if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

# Block stop — Claude will call MCP add_memory then stop naturally
jq -cn '{
  decision: "block",
  reason: "Store 1-3 learnings via add_memory before stopping."
}' 2>/dev/null || true

exit 0
