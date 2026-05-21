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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_identity.sh
. "$SCRIPT_DIR/_identity.sh"

# Detect stack traces and error patterns in the prompt (no API needed)
HAS_ERROR=""
if echo "$PROMPT" | grep -qiE '(Traceback|Error:|Exception:|panic:|FAILED|fatal:| at .+\.[a-z]+:[0-9]+)'; then
  HAS_ERROR="true"
fi

# Detect file paths in the prompt (no API needed)
FILE_PATHS=$(echo "$PROMPT" | grep -oE '([a-zA-Z0-9_./-]+\.(py|ts|tsx|js|jsx|rs|go|rb|java|sh|yaml|yml|json|toml|md|sql|css|html))\b' 2>/dev/null | head -5 || echo "")

# Telemetry (background, fire-and-forget)
_TELEM_ARGS=""
[ -n "$HAS_ERROR" ] && _TELEM_ARGS="$_TELEM_ARGS --error_detected"
[ -n "$FILE_PATHS" ] && _TELEM_ARGS="$_TELEM_ARGS --file_paths_detected"
python3 "$SCRIPT_DIR/telemetry.py" user_prompt $_TELEM_ARGS 2>/dev/null &

# No API key — emit detections only, skip search rubric
if [ -z "${MEM0_API_KEY:-}" ]; then
  if [ -n "$HAS_ERROR" ]; then
    echo "**ERROR DETECTED in prompt.** Set MEM0_API_KEY to search past debugging context."
  fi
  if [ -n "$FILE_PATHS" ]; then
    echo "**FILE PATHS detected:** \`$FILE_PATHS\`"
  fi
  exit 0
fi
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
EOF

if [ -n "$HAS_ERROR" ]; then
  cat <<EOF

**ERROR DETECTED in prompt.** You SHOULD search mem0 for prior occurrences:
- \`search_memories(query="<error class or message>", filters={"AND": [{"user_id": "$USER_ID"}, {"app_id": "$MEM0_PROJECT_ID"}, {"metadata": {"type": "anti_pattern"}}]})\`
- \`search_memories(query="<module or file from stack trace>", filters={"AND": [{"user_id": "$USER_ID"}, {"app_id": "$MEM0_PROJECT_ID"}, {"metadata": {"type": "task_learning"}}]})\`
This surfaces past debugging context and known failure modes.
EOF
fi

if [ -n "$FILE_PATHS" ]; then
  cat <<EOF

**FILE PATHS detected:** \`$FILE_PATHS\`
Search mem0 for context about these files:
- \`search_memories(query="<filename without extension>", filters={"AND": [{"user_id": "$USER_ID"}, {"app_id": "$MEM0_PROJECT_ID"}]})\`
Memories tagged with \`metadata.files\` containing these paths will surface via text match.
EOF
fi

cat <<EOF

**If searching, do it well:**
- Run **2-4 parallel** \`search_memories\` calls with different angles, not one
  query that echoes the user's prompt.
- Phrase queries as **nouns** ("auth module decisions"), not full sentences.
- Filter shape: the root must be a logical operator (\`AND\` / \`OR\` / \`NOT\`)
  with an array, and metadata uses a **nested** object (not dotted keys).
  Combine \`user_id\` + \`app_id\` with one \`metadata.type\` clause per call:
  - \`{"AND": [{"user_id": "$USER_ID"}, {"app_id": "$MEM0_PROJECT_ID"}, {"metadata": {"type": "decision"}}]}\` -- design / architecture
  - \`{"AND": [{"user_id": "$USER_ID"}, {"app_id": "$MEM0_PROJECT_ID"}, {"metadata": {"type": "anti_pattern"}}]}\` -- debugging, error handling
  - \`{"AND": [{"user_id": "$USER_ID"}, {"app_id": "$MEM0_PROJECT_ID"}, {"metadata": {"type": "user_preference"}}]}\` -- tooling, stack, style
  - \`{"AND": [{"user_id": "$USER_ID"}, {"app_id": "$MEM0_PROJECT_ID"}, {"metadata": {"type": "convention"}}]}\` -- established patterns
  - Or scope with just \`{"AND": [{"user_id": "$USER_ID"}, {"app_id": "$MEM0_PROJECT_ID"}]}\` when no metadata filter fits.
- **Recency boost:** For state-related queries ("where were we", "current task", "latest"), add a \`created_at\` filter: \`{"created_at": {"gte": "<90 days ago YYYY-MM-DD>"}}\`. Skip recency for durable facts (conventions, decisions).
- Empty results are normal -- proceed without context.
EOF

exit 0
