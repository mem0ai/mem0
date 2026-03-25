#!/usr/bin/env bash
# Hook: Stop
#
# Fires when Claude finishes responding.
# Reminds Claude to store any unsaved learnings, then spawns a background
# process to capture transcript state via the Mem0 REST API directly.
#
# Input:  JSON on stdin with stop_hook_active, transcript_path, cwd
# Output: Text that becomes Claude's context (exit 0), or nothing
#
# IMPORTANT: Check stop_hook_active to avoid infinite loops.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

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

# Capture transcript state in the background via Mem0 REST API
echo "$INPUT" | python3 "$SCRIPT_DIR/on_pre_compact.py" --source=session-end 2>/dev/null &

exit 0
