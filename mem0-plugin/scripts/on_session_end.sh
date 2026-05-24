#!/usr/bin/env bash
set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

INPUT=$(cat)
REASON=$(echo "$INPUT" | jq -r '.reason // "other"' 2>/dev/null || echo "other")

REPORT=$(python3 "$SCRIPT_DIR/session_stats.py" report 2>/dev/null || echo "")
if [ -n "$REPORT" ] && [ "$REPORT" != "Session: no memory operations." ]; then
  mkdir -p "$HOME/.mem0" 2>/dev/null || true
  _LOG_FILE="$HOME/.mem0/session-log.md"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | $REPORT" >> "$_LOG_FILE" 2>/dev/null || true
  _LINE_COUNT=$(wc -l < "$_LOG_FILE" 2>/dev/null || echo 0)
  if [ "$_LINE_COUNT" -gt 500 ]; then
    tail -500 "$_LOG_FILE" > "${_LOG_FILE}.tmp" 2>/dev/null && mv "${_LOG_FILE}.tmp" "$_LOG_FILE" 2>/dev/null || true
  fi
fi

python3 "$SCRIPT_DIR/telemetry.py" session_end --reason="$REASON" 2>/dev/null &

find "$HOME/.mem0" -name ".captured_*" -mtime +7 -delete 2>/dev/null || true

exit 0
