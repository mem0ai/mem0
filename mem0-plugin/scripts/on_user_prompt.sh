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

# Rubric dedup: only inject full rubric once per session.
# Key on session ID (from stdin JSON) to avoid cross-session interference.
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""' 2>/dev/null || echo "")
RUBRIC_DIR="${MEM0_RUBRIC_DIR:-/tmp}"
if [ -n "$SESSION_ID" ]; then
  RUBRIC_FLAG="$RUBRIC_DIR/mem0_rubric_${SESSION_ID}"
else
  RUBRIC_FLAG="$RUBRIC_DIR/mem0_rubric_injected_${USER}"
fi
RUBRIC_ALREADY_SHOWN=""
if [ -f "$RUBRIC_FLAG" ]; then
  RUBRIC_ALREADY_SHOWN="true"
fi

# Detect stack traces and error patterns in the prompt (no API needed)
HAS_ERROR=""
if echo "$PROMPT" | grep -qE '(Traceback|panic:)'; then
  HAS_ERROR="true"
elif echo "$PROMPT" | grep -qE '^\s*fatal: '; then
  HAS_ERROR="true"
elif [ "$(echo "$PROMPT" | grep -cE '(Error:|Exception:|FAIL:)')" -ge 2 ]; then
  HAS_ERROR="true"
fi

# Detect file paths in the prompt (no API needed)
FILE_PATHS=$(echo "$PROMPT" | grep -oE '([a-zA-Z0-9_./-]+\.(py|ts|tsx|js|jsx|rs|go|rb|java|sh|yaml|yml|json|toml|md|sql|css|html))\b' 2>/dev/null | head -5 || echo "")

# Detect session-resume patterns
HAS_RESUME=""
if echo "$PROMPT" | grep -qiE '(where (did )?(we|I) (leave|left) off|continue (from )?(where|last)|what were we (working|doing)|pick up where|resume (from |where)|what.s the (current|latest) (state|status)|catch me up|where are we)'; then
  HAS_RESUME="true"
fi

# Telemetry (background, fire-and-forget)
_TELEM_ARGS=""
[ -n "$HAS_ERROR" ] && _TELEM_ARGS="$_TELEM_ARGS --error_detected"
[ -n "$FILE_PATHS" ] && _TELEM_ARGS="$_TELEM_ARGS --file_paths_detected"
[ -n "$HAS_RESUME" ] && _TELEM_ARGS="$_TELEM_ARGS --resume_detected"
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

if [ -n "$HAS_RESUME" ]; then
  RESUME_RESULTS=$(PYTHONPATH="$SCRIPT_DIR" MEM0_SEARCH_USER="$USER_ID" python3 -c "
import os, sys
sys.path.insert(0, os.environ.get('PYTHONPATH', '.'))
from _search import search_memories, format_results_for_context

api_key = os.environ.get('MEM0_API_KEY', '')
user_id = os.environ.get('MEM0_SEARCH_USER', 'default')
project_id = os.environ.get('MEM0_PROJECT_ID', 'unknown')

state = search_memories(api_key, user_id, project_id, 'session state current task', metadata_type='session_state', top_k=3)
decisions = search_memories(api_key, user_id, project_id, 'recent decisions and learnings', metadata_type='decision', top_k=3)

all_r = state + decisions
seen = set()
unique = []
for m in all_r:
    mid = m.get('id', '')
    if mid not in seen:
        seen.add(mid)
        unique.append(m)

if unique:
    print(format_results_for_context(unique, heading='Session context recovered from mem0'))
    print()
    print('Use these memories to resume work. Do NOT ask the user to repeat context that is already in these memories.')
else:
    print('No session state found in mem0. Ask the user what they want to continue.')
" 2>/dev/null || echo "")

  if [ -n "$RESUME_RESULTS" ]; then
    echo ""
    echo "$RESUME_RESULTS"
  fi
fi

if [ -z "$RUBRIC_ALREADY_SHOWN" ]; then
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
  touch "$RUBRIC_FLAG" 2>/dev/null || true
fi

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
Search mem0 for context about these files using the \`contains\` operator on \`metadata.files\`:
- \`search_memories(query="<filename>", filters={"AND": [{"user_id": "$USER_ID"}, {"app_id": "$MEM0_PROJECT_ID"}, {"metadata.files": {"contains": "<filename>"}}]})\`
- Also run a broader text search without the files filter as fallback:
- \`search_memories(query="<filename without extension>", filters={"AND": [{"user_id": "$USER_ID"}, {"app_id": "$MEM0_PROJECT_ID"}]})\`
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
