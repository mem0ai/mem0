#!/usr/bin/env bash
# Hook: TaskCompleted
#
# Fires when a task is marked as completed. Reminds Claude to extract
# and store learnings via the mem0 MCP tools.
#
# Input:  JSON on stdin with task_id, task_subject, task_description
# Output: Text that becomes feedback to the model (exit 0)

set -euo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

INPUT=$(cat)
TASK_SUBJECT=$(echo "$INPUT" | jq -r '.task_subject // "unknown task"' 2>/dev/null || echo "unknown task")

cat <<EOF
Task completed: "$TASK_SUBJECT"

Extract key learnings from this completed task and store them using the mem0 \`add_memory\` tool:

1. What strategy worked well? -> Store with metadata \`{"type": "task_learning"}\`
2. Were there failed approaches before finding the solution? -> Store with metadata \`{"type": "anti_pattern"}\`
3. Were there architectural decisions? -> Store with metadata \`{"type": "decision"}\`
4. Any new conventions or patterns established? -> Store with metadata \`{"type": "convention"}\`

Memories can be as detailed as needed — include full context, reasoning, code snippets, and examples.
Only store genuinely useful learnings — skip if the task was trivial.
EOF

exit 0
