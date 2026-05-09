#!/usr/bin/env bash
# Hook: Stop (Codex)
#
# Fires when Codex finishes a turn. Reminds the agent to persist any
# important learnings via the mem0 MCP tools before the turn closes.
#
# Input:  JSON on stdin with session_id, turn_id, stop_hook_active,
#         last_assistant_message, transcript_path, cwd,
#         hook_event_name, model
# Output: JSON on stdout (Codex rejects plain text on Stop).
#         - stop_hook_active=true  -> {"continue": true}  (let the turn end)
#         - stop_hook_active=false -> {"decision":"block","reason":"..."}
#           (continue the turn with the reminder as context)
#
# We must respect stop_hook_active or we'd loop forever: every "block"
# reopens the turn, which triggers Stop again when the agent settles.

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

INPUT=$(cat)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")

if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  printf '{"continue":true}\n'
  exit 0
fi

REASON=$(cat <<'EOF'
Before finishing, check if there are important learnings from this interaction that should be persisted using the mem0 `add_memory` tool:

1. Were any significant decisions made? -> Store with metadata `{"type": "decision"}`
2. Were any new patterns or strategies discovered? -> Store with metadata `{"type": "task_learning"}`
3. Did any approach fail? -> Store with metadata `{"type": "anti_pattern"}`
4. Did you learn anything about the user's preferences? -> Store with metadata `{"type": "user_preference"}`
5. Were there environment/setup discoveries? -> Store with metadata `{"type": "environmental"}`

Memories can be as detailed as needed — include full context, reasoning, code snippets, file paths, and examples. Longer, searchable memories are more valuable than vague one-liners.

If nothing notable happened in this interaction, it's fine to skip. Only store genuinely useful learnings.
EOF
)

jq -cn --arg reason "$REASON" '{decision:"block", reason:$reason}'
exit 0
