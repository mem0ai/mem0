#!/usr/bin/env bash
# Hook: TaskCompleted
#
# Fires when a task is marked as completed. Reminds Claude to extract
# and store learnings via the mem0 MCP tools.
#
# Input:  JSON on stdin with task_id, task_subject, task_description
# Output: Text that becomes feedback to the model (exit 0)

# Intentionally omit -e so the reminder always emits even if identity resolution fails.
set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

INPUT=$(cat)
TASK_SUBJECT=$(echo "$INPUT" | jq -r '.task_subject // "unknown task"' 2>/dev/null || echo "unknown task")

_PROJECT="${MEM0_PROJECT_ID:-unknown}"

cat <<EOF
Task completed: "$TASK_SUBJECT"

Store 0-2 key learnings via \`add_memory\` with \`app_id="$_PROJECT"\`. Use types: \`decision\`, \`task_learning\`, \`anti_pattern\`, or \`convention\`. Skip if trivial.
EOF

# Telemetry (background, fire-and-forget)
python3 "$SCRIPT_DIR/telemetry.py" task_completed 2>/dev/null &

exit 0
