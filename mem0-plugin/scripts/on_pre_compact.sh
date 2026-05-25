#!/usr/bin/env bash
# Hook: PreCompact
#
# Fires BEFORE context compaction. Captures session state via REST API
# in the background. Runs silently — no output to user.

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT=$(cat)

python3 "$SCRIPT_DIR/telemetry.py" pre_compact 2>/dev/null &

# Capture in background, no stdout
_TMP="/tmp/mem0_precompact_input_$$.json"
printf '%s' "$INPUT" > "$_TMP" 2>/dev/null
(python3 "$SCRIPT_DIR/on_pre_compact.py" --source=pre-compaction < "$_TMP" 2>/dev/null; rm -f "$_TMP") &

exit 0
