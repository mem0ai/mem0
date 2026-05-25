#!/usr/bin/env bash
# Hook: TaskCompleted
#
# Fires when a task is marked as completed. Stdout is fed back to Claude
# as context, prompting it to capture learnings.
#
# Input:  JSON on stdin with task_id, task_subject, task_description
# Output: Text feedback to Claude (exit 0)

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

INPUT=$(cat)
TASK_SUBJECT=$(echo "$INPUT" | jq -r '.task_subject // ""' 2>/dev/null || echo "")

# Skip trivial or unknown tasks
if [ -z "$TASK_SUBJECT" ] || [ "$TASK_SUBJECT" = "unknown task" ] || [ ${#TASK_SUBJECT} -lt 10 ]; then
  exit 0
fi

_PROJECT="${MEM0_PROJECT_ID:-unknown}"

echo "Task completed: ${TASK_SUBJECT}. Learnings (decision, task_learning, anti_pattern, convention) are captured via add_memory with app_id=${_PROJECT}."

# Telemetry (background, fire-and-forget)
python3 "$SCRIPT_DIR/telemetry.py" task_completed 2>/dev/null &

exit 0
