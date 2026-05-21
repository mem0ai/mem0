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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_identity.sh
. "$SCRIPT_DIR/_identity.sh"

INPUT=$(cat)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")

if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  printf '{"continue":true}\n'
  exit 0
fi

# Telemetry: fire before report() deletes stats file
_TELEM_CAT=$(python3 "$SCRIPT_DIR/session_stats.py" peek 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('categories',[])))" 2>/dev/null || echo "0")
python3 "$SCRIPT_DIR/telemetry.py" stop --categories_count="$_TELEM_CAT" 2>/dev/null &

# Session-end report (best-effort, must not break JSON output)
REPORT=$(python3 "$SCRIPT_DIR/session_stats.py" report 2>/dev/null || echo "")
REPORT_BLOCK=""
if [ -n "$REPORT" ]; then
  REPORT_BLOCK="---\nmem0 $REPORT\n---\n\n"
  mkdir -p "$HOME/.mem0" 2>/dev/null || true
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | $REPORT" >> "$HOME/.mem0/session-log.md" 2>/dev/null || true
fi

REASON=$(cat <<EOF
${REPORT_BLOCK}Before finishing, check if there are important learnings from this interaction that should be persisted using the mem0 \`add_memory\` tool:

1. Were any significant decisions made? -> Store with metadata \`{"type": "decision"}\`
2. Were any new patterns or strategies discovered? -> Store with metadata \`{"type": "task_learning"}\`
3. Did any approach fail? -> Store with metadata \`{"type": "anti_pattern"}\`
4. Did you learn anything about the user's preferences? -> Store with metadata \`{"type": "user_preference"}\`
5. Were there environment/setup discoveries? -> Store with metadata \`{"type": "environmental"}\`

Memories can be as detailed as needed — include full context, reasoning, code snippets, file paths, and examples. Longer, searchable memories are more valuable than vague one-liners.

Always include \`app_id\` (the active project_id from SessionStart) as a top-level parameter in every \`add_memory\` call.

If nothing notable happened in this interaction, it's fine to skip. Only store genuinely useful learnings.
EOF
)

jq -cn --arg reason "$REASON" '{decision:"block", reason:$reason}'

# Capture transcript state in the background via Mem0 REST API
echo "$INPUT" | python3 "$SCRIPT_DIR/on_pre_compact.py" --source=session-end 2>/dev/null &

exit 0
