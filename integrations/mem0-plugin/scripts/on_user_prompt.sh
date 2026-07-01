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

# Honor auto_search setting: when false, skip all automatic searches and
# rubric injection.  The agent can still call search_memories via MCP
# manually — this only disables the hook-driven auto-retrieval that
# consumes the monthly retrieval quota.
if [ "${MEM0_AUTO_SEARCH:-true}" = "false" ]; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_identity.sh
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

# Rubric dedup: only inject full rubric once per session.
# Key on session ID to avoid cross-session interference.
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""' 2>/dev/null || echo "")
if [ -z "$SESSION_ID" ]; then
  _SID_FILE="/tmp/mem0_session_id_${USER:-default}"
  [ -f "$_SID_FILE" ] && SESSION_ID=$(cat "$_SID_FILE" 2>/dev/null) || true
fi
if [ -z "$SESSION_ID" ]; then
  SESSION_ID="default_${USER:-unknown}"
fi
RUBRIC_DIR="${MEM0_RUBRIC_DIR:-/tmp}"
RUBRIC_FLAG="$RUBRIC_DIR/mem0_rubric_${SESSION_ID}"
RUBRIC_ALREADY_SHOWN=""
if [ -f "$RUBRIC_FLAG" ]; then
  RUBRIC_ALREADY_SHOWN="true"
fi

# Track message count for periodic memory-save nudges.
# Every 5th substantial message, remind the agent to store learnings.
MSG_COUNT_FILE="/tmp/mem0_msg_count_${USER:-default}"
MSG_COUNT=0
if [ -f "$MSG_COUNT_FILE" ]; then
  MSG_COUNT=$(cat "$MSG_COUNT_FILE" 2>/dev/null || echo "0")
fi
MSG_COUNT=$((MSG_COUNT + 1))
printf '%s' "$MSG_COUNT" > "$MSG_COUNT_FILE" 2>/dev/null || true
NEEDS_SAVE_NUDGE=""
if [ $((MSG_COUNT % 5)) -eq 0 ] && [ "$MSG_COUNT" -gt 0 ]; then
  NEEDS_SAVE_NUDGE="true"
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

# Detect explicit memory-save intent
HAS_REMEMBER=""
if echo "$PROMPT" | grep -qiE '(remember (this|that)|save (this|that) (fact|info|memory|note)|store (this|that)|don.t forget (this|that)|keep (this|that) in (mind|memory))'; then
  HAS_REMEMBER="true"
fi

# Telemetry (background, fire-and-forget)
_TELEM_ARGS=""
[ -n "$HAS_ERROR" ] && _TELEM_ARGS="$_TELEM_ARGS --error_detected"
[ -n "$FILE_PATHS" ] && _TELEM_ARGS="$_TELEM_ARGS --file_paths_detected"
[ -n "$HAS_RESUME" ] && _TELEM_ARGS="$_TELEM_ARGS --resume_detected"
[ -n "$HAS_REMEMBER" ] && _TELEM_ARGS="$_TELEM_ARGS --remember_detected"
python3 "$SCRIPT_DIR/telemetry.py" user_prompt $_TELEM_ARGS 2>/dev/null &

# No API key — emit detections only, skip search rubric
if [ -z "${MEM0_API_KEY:-}" ]; then
  _PROMPT_CTX=""
  if [ -n "$HAS_ERROR" ]; then
    _PROMPT_CTX="Error detected in prompt. Set MEM0_API_KEY to search past debugging context."
  fi
  if [ -n "$FILE_PATHS" ]; then
    _PROMPT_CTX="${_PROMPT_CTX:+${_PROMPT_CTX}\n}File paths detected: ${FILE_PATHS}"
  fi
  if [ -n "$_PROMPT_CTX" ]; then
    jq -cn --arg ctx "$_PROMPT_CTX" '{
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext: $ctx
      }
    }'
  fi
  exit 0
fi
USER_ID="$MEM0_RESOLVED_USER_ID"

_PROMPT_CTX=""

if [ -n "$HAS_RESUME" ]; then
  RESUME_RESULTS=$(PYTHONPATH="$SCRIPT_DIR" MEM0_SEARCH_USER="$USER_ID" python3 -c "
import os, sys
sys.path.insert(0, os.environ.get('PYTHONPATH', '.'))
from _search import search_memories, format_results_for_context, should_rerank

api_key = os.environ.get('MEM0_API_KEY', '')
user_id = os.environ.get('MEM0_SEARCH_USER', 'default')
project_id = os.environ.get('MEM0_PROJECT_ID', 'unknown')
rerank = should_rerank()

state = search_memories(api_key, user_id, project_id, 'session state current task', metadata_type='session_state', top_k=3, rerank=rerank)
decisions = search_memories(api_key, user_id, project_id, 'recent decisions and learnings', metadata_type='decision', top_k=3, rerank=rerank)

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
    print('These memories provide context for resuming work.')
else:
    print('No session state found in mem0.')
" 2>/dev/null || echo "")

  if [ -n "$RESUME_RESULTS" ]; then
    _PROMPT_CTX="${RESUME_RESULTS}"
  fi
fi

if [ -n "$HAS_REMEMBER" ]; then
  _PROMPT_CTX="${_PROMPT_CTX:+${_PROMPT_CTX}\n}Remember intent detected. The /mem0:remember skill auto-classifies, sets confidence=1.0, and stores verbatim."
fi

if [ -z "$RUBRIC_ALREADY_SHOWN" ]; then
  _PROMPT_CTX="${_PROMPT_CTX:+${_PROMPT_CTX}\n}Mem0 searches apply when user references past work, decision questions, errors, or non-trivial tasks. Queries use noun-phrases, 2-4 parallel calls with different metadata.type filters, and include user_id + app_id."
  touch "$RUBRIC_FLAG" 2>/dev/null || true
fi

if [ -n "$HAS_ERROR" ]; then
  _PROMPT_CTX="${_PROMPT_CTX:+${_PROMPT_CTX}\n}Error detected in prompt. Prior occurrences are available in mem0 via anti_pattern and task_learning type filters."
fi

if [ -n "$FILE_PATHS" ]; then
  _PROMPT_CTX="${_PROMPT_CTX:+${_PROMPT_CTX}\n}File paths detected: ${FILE_PATHS}"
fi

# Auto-capture: directly call mem0 API in background every 3rd message.
# At MSG_COUNT=3 the 3rd response isn't in the transcript yet (hook fires
# before Claude responds), so we capture 4 exchanges instead of 3. The
# overlapping window ensures the next batch (MSG_COUNT=6) picks up the
# exchange that was incomplete in the previous batch.
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""' 2>/dev/null || echo "")
if [ "${MEM0_AUTO_SAVE:-true}" != "false" ] && [ $((MSG_COUNT % 3)) -eq 0 ] && [ "$MSG_COUNT" -gt 0 ] && [ -n "$TRANSCRIPT_PATH" ]; then
  python3 "$SCRIPT_DIR/auto_capture.py" "$TRANSCRIPT_PATH" 2>/dev/null &
fi

# Prompt-based nudge as fallback when auto-capture hasn't run yet.
_ADDS=0
_STATS_FILE="/tmp/mem0_session_stats_${USER:-default}.json"
if [ -f "$_STATS_FILE" ]; then
  _ADDS=$(python3 -c "import json; print(json.load(open('$_STATS_FILE')).get('adds',0))" 2>/dev/null || echo "0")
fi

if [ "$MSG_COUNT" -ge 3 ] && [ "$_ADDS" -lt "$((MSG_COUNT / 3))" ]; then
  _PROMPT_CTX="${_PROMPT_CTX:+${_PROMPT_CTX}\n}After responding, store any new decisions, learnings, or preferences from this exchange via add_memory. Keep it to 1 sentence per memory."
fi

if [ -n "$_PROMPT_CTX" ]; then
  jq -cn --arg ctx "$_PROMPT_CTX" '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: $ctx
    }
  }'
fi

exit 0
