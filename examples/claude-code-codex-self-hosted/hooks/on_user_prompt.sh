#!/usr/bin/env bash
# Hook: UserPromptSubmit
#
# Fires on every user message. Searches memories relevant to the current
# prompt and injects the top matches so relevant context is guaranteed to be
# in the agent's context window, not left for the agent to fetch lazily.
#
# Input:  JSON on stdin (prompt, session_id, cwd)
# Output: hookSpecificOutput.additionalContext (Claude Code) or plain text (Codex)
#
# Must never block the prompt: any failure exits 0 silently.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=mem0_env.sh
. "$SCRIPT_DIR/mem0_env.sh" 2>/dev/null || exit 0

if ! mem0_ready; then
  exit 0
fi

INPUT=$(cat)
PROMPT=$(echo "$INPUT" | jq -r '.prompt // ""' 2>/dev/null || echo "")

# Acknowledgements and short replies don't warrant memory context.
if [ ${#PROMPT} -lt 20 ]; then
  exit 0
fi

RESULTS=$(mem0_search "${PROMPT}")
CONTEXT=$(mem0_format_results "${RESULTS}")

if [ -z "$CONTEXT" ]; then
  exit 0
fi

HEADER="Relevant memories from previous sessions (self-hosted Mem0):"
BODY="${HEADER}
${CONTEXT}"

mem0_emit_context "UserPromptSubmit" "$BODY"
exit 0
