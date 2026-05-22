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

Extract key learnings from this completed task and store them using the mem0 \`add_memory\` tool:

1. What strategy worked well? -> Store with metadata \`{"type": "task_learning"}\`
2. Were there failed approaches before finding the solution? -> Store with metadata \`{"type": "anti_pattern"}\`
3. Were there architectural decisions? -> Store with metadata \`{"type": "decision"}\`
4. Any new conventions or patterns established? -> Store with metadata \`{"type": "convention"}\`

Memories can be as detailed as needed — include full context, reasoning, code snippets, and examples.
Only store genuinely useful learnings — skip if the task was trivial.
Include \`app_id\` = \`"$_PROJECT"\` as a top-level parameter in every \`add_memory\` call (not in metadata).
EOF

# Telemetry (background, fire-and-forget)
python3 "$SCRIPT_DIR/telemetry.py" task_completed 2>/dev/null &

exit 0
