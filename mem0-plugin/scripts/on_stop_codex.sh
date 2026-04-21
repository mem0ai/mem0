#!/usr/bin/env bash
# Hook: Stop (Codex)
#
# Fires when Codex finishes a turn. Reminds the agent to persist any
# important learnings via the mem0 MCP tools before the turn closes.
#
# Input:  JSON on stdin with session_id, transcript_path, cwd,
#         hook_event_name, model, turn_id, stop_hook_active,
#         last_assistant_message
# Output: Text fed back as additional context (exit 0)
#
# IMPORTANT: Respect stop_hook_active to avoid feedback loops when this
# hook's output triggers another turn.

set -uo pipefail

INPUT=$(cat)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")

if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

cat <<'EOF'
Before finishing, check if there are important learnings from this interaction that should be persisted using the mem0 `add_memory` tool:

1. Were any significant decisions made? -> Store with metadata `{"type": "decision"}`
2. Were any new patterns or strategies discovered? -> Store with metadata `{"type": "task_learning"}`
3. Did any approach fail? -> Store with metadata `{"type": "anti_pattern"}`
4. Did you learn anything about the user's preferences? -> Store with metadata `{"type": "user_preference"}`
5. Were there environment/setup discoveries? -> Store with metadata `{"type": "environmental"}`

Memories can be as detailed as needed — include full context, reasoning, code snippets, file paths, and examples. Longer, searchable memories are more valuable than vague one-liners.

If nothing notable happened in this interaction, it's fine to skip. Only store genuinely useful learnings.
EOF

exit 0
