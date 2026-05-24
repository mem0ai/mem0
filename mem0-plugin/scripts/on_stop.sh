#!/usr/bin/env bash
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

_TELEM_CAT=$(python3 "$SCRIPT_DIR/session_stats.py" peek 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('categories',[])))" 2>/dev/null || echo "0")
python3 "$SCRIPT_DIR/telemetry.py" stop --categories_count="$_TELEM_CAT" 2>/dev/null &

cat <<'EOF'
Store 0-2 durable facts from this turn via `add_memory` — only decisions, anti-patterns, or conventions that would help a future agent. Skip if nothing new was learned.
EOF

exit 0
