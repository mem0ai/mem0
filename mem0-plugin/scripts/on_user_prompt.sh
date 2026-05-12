#!/usr/bin/env bash
# Hook: UserPromptSubmit
#
# Fires on every user message. Instead of pre-searching mem0 with the
# raw prompt, this injects a decision rubric telling the agent when
# and how to search itself. The agent has more context than this
# script does -- let it decide.
#
# Input:  JSON on stdin (prompt, session_id, cwd, transcript_path)
# Output: Decision rubric injected into Claude's context (exit 0)

# Intentionally omit -e so the script always exits 0 even if jq fails --
# must never block the user's prompt.
set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

INPUT=$(cat)
PROMPT=$(echo "$INPUT" | jq -r '.prompt // ""' 2>/dev/null || echo "")

# Acknowledgements and short replies don't warrant memory context
if [ ${#PROMPT} -lt 20 ]; then
  exit 0
fi

# No API key means the agent can't search anyway
if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_identity.sh
. "$SCRIPT_DIR/_identity.sh"
USER_ID="$MEM0_RESOLVED_USER_ID"

cat <<EOF
## Memory check

Before responding, decide whether persistent memory context from mem0 would
improve your answer. The agent -- not this hook -- owns this decision.

**Search WHEN** the user:
- references past work, decisions, or things "we" built
- asks "how should we...", "best way to...", or any decision-style question
- hits an error, bug, or asks for debugging help
- requests work that touches their stack, tools, conventions, or preferences
- starts a non-trivial task in a known project

**Skip WHEN:**
- the prompt is an acknowledgement or continuation
- the user is *stating* new info -- that's a write trigger (\`add_memory\`), not a search
- it's a pure syntax / factual question answerable from general knowledge
- you already searched this scope earlier in the turn

**If searching, do it well:**
- Run **2-4 parallel** \`search_memories\` calls with different angles, not one
  query that echoes the user's prompt.
- Phrase queries as **nouns** ("auth module decisions"), not full sentences.
- Filter shape: the root must be a logical operator (\`AND\` / \`OR\` / \`NOT\`)
  with an array, and metadata uses a **nested** object (not dotted keys).
  Combine \`user_id\` with one \`metadata.type\` clause per call:
  - \`{"AND": [{"user_id": "$USER_ID"}, {"metadata": {"type": "decision"}}]}\` -- design / architecture
  - \`{"AND": [{"user_id": "$USER_ID"}, {"metadata": {"type": "anti_pattern"}}]}\` -- debugging, error handling
  - \`{"AND": [{"user_id": "$USER_ID"}, {"metadata": {"type": "user_preference"}}]}\` -- tooling, stack, style
  - \`{"AND": [{"user_id": "$USER_ID"}, {"metadata": {"type": "convention"}}]}\` -- established patterns
- Or scope with just \`{"AND": [{"user_id": "$USER_ID"}]}\` when no metadata filter fits.
- Empty results are normal -- proceed without context.
EOF

exit 0
