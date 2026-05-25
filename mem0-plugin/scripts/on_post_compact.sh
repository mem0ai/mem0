#!/usr/bin/env bash
# Hook: PostCompact (matcher: manual|auto)
#
# Fires after context compaction completes. Runs silently — recovery
# is handled by SessionStart hook with source=compact.

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

INPUT=$(cat)
TRIGGER=$(echo "$INPUT" | jq -r '.trigger // "auto"' 2>/dev/null || echo "auto")
RETAINED=$(echo "$INPUT" | jq -r '.messages_retained // "?"' 2>/dev/null || echo "?")
REMOVED=$(echo "$INPUT" | jq -r '.messages_removed // "?"' 2>/dev/null || echo "?")

# Telemetry (background)
python3 "$SCRIPT_DIR/telemetry.py" post_compact --trigger="$TRIGGER" --retained="$RETAINED" --removed="$REMOVED" 2>/dev/null &

exit 0
