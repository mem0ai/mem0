#!/usr/bin/env bash
# Kimi Code hook adapter.
#
# Kimi Code's hook contract is close to Claude Code's but differs in four ways
# that the mem0 hook scripts care about. Rather than fork nine scripts, every
# Kimi hook entry in .kimi-plugin/plugin.json routes through this shim.
#
#   1. cwd     Kimi runs hook commands with cwd forced to the PLUGIN root
#              (agent-core-v2 src/app/plugin/manager.ts -> enabledHooks() sets
#              `cwd: record.root`). The real project directory only arrives as
#              the payload's `cwd` field. _project.sh resolves MEM0_PROJECT_ID
#              from $PWD/`git remote`, so we chdir into the payload cwd first.
#
#   2. stdin   Kimi sends snake_case JSON like Claude, but:
#                - `prompt` is a ContentPart[] array, not a string
#                - PostToolUse sends `tool_output`, not `tool_response`
#                - file tools use `tool_input.path`, not `tool_input.file_path`
#                - plugin MCP tools are `mcp__plugin-mem0_mem0__*` (hyphen),
#                  not Claude's `mcp__plugin_mem0_mem0__*`
#                - there is NO `transcript_path` (no equivalent exists)
#              We normalise the first four into the Claude shape.
#
#   3. stdout  Kimi's hook stdout parser (agent-core-v2
#              src/agent/externalHooks/runner.ts -> HookJsonOutputSchema) only
#              understands top-level `message`, `hookSpecificOutput.message`,
#              `hookSpecificOutput.permissionDecision` and
#              `hookSpecificOutput.permissionDecisionReason`.
#              `additionalContext` and `updatedInput` are NOT recognised.
#              Raw (non-JSON) stdout IS appended to context for UserPromptSubmit
#              (user-prompt.ts -> userPromptHookMessage falls back to stdout), so
#              we unwrap additionalContext into plain text.
#
#   4. exit    Same as Claude: 0 = allow, 2 = block (stderr is the reason),
#              any other code / timeout = fail-open.
#
# Usage: kimi_hook_shim.sh <script-name.sh> [args...]

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

[ $# -ge 1 ] || exit 0
TARGET_NAME="$1"
shift
TARGET="$SCRIPT_DIR/$TARGET_NAME"
[ -f "$TARGET" ] || exit 0

# Telemetry attribution (telemetry.py::detect_platform honours MEM0_PLATFORM).
export MEM0_PLATFORM="${MEM0_PLATFORM:-kimi}"

RAW=$(cat)

_TMP_BASE="${TMPDIR:-/tmp}"
IN_FILE="$_TMP_BASE/mem0_kimi_in_$$"
OUT_FILE="$_TMP_BASE/mem0_kimi_out_$$"
trap 'rm -f "$IN_FILE" "$OUT_FILE"' EXIT

HAVE_JQ=""
command -v jq >/dev/null 2>&1 && HAVE_JQ="true"

# ---------------------------------------------------------------- stdin shape
NORM=""
if [ -n "$HAVE_JQ" ]; then
  NORM=$(printf '%s' "$RAW" | jq -c '
    def flat_prompt:
      if type == "array" then
        [ .[]? | if type == "object" then (.text // "") elif type == "string" then . else "" end ]
        | map(select(. != "")) | join("\n")
      elif type == "string" then .
      else "" end;
    . as $in
    | (if has("prompt") then .prompt = ($in.prompt | flat_prompt) else . end)
    | (if (has("tool_response") | not) and (.tool_output != null)
         then .tool_response = .tool_output else . end)
    | (if ((.tool_input | type) == "object") and (.tool_input.file_path == null) and (.tool_input.path != null)
         then .tool_input.file_path = .tool_input.path else . end)
    | (if ((.tool_name | type) == "string") and (.tool_name | startswith("mcp__")) and (.tool_name | test("mem0"))
         then .tool_name = (.tool_name | gsub("-"; "_")) else . end)
  ' 2>/dev/null)
fi
[ -n "$NORM" ] || NORM="$RAW"

printf '%s' "$NORM" >"$IN_FILE" 2>/dev/null || exit 0

# ------------------------------------------------------------------- real cwd
if [ -n "$HAVE_JQ" ]; then
  PROJECT_CWD=$(printf '%s' "$NORM" | jq -r '.cwd // ""' 2>/dev/null || printf '')
  if [ -n "$PROJECT_CWD" ] && [ -d "$PROJECT_CWD" ]; then
    cd "$PROJECT_CWD" 2>/dev/null || true
  fi
fi

# ------------------------------------------------------------------- dispatch
# Redirect (not pipe) stdout so backgrounded children inside the hook scripts
# cannot hold the shim open until Kimi's timeout fires.
bash "$TARGET" "$@" <"$IN_FILE" >"$OUT_FILE"
CODE=$?

OUT=$(cat "$OUT_FILE" 2>/dev/null || printf '')

# --------------------------------------------------------------- stdout shape
if [ -n "$OUT" ] && [ -n "$HAVE_JQ" ] && printf '%s' "$OUT" | jq -e 'type == "object"' >/dev/null 2>&1; then
  if printf '%s' "$OUT" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null 2>&1; then
    # Kimi understands deny natively — pass the envelope straight through.
    printf '%s' "$OUT"
  else
    CTX=$(printf '%s' "$OUT" | jq -r '
      (.hookSpecificOutput.additionalContext
        // .additionalContext
        // .message
        // .hookSpecificOutput.message
        // "")
      | gsub("\\\\n"; "\n")' 2>/dev/null || printf '')
    [ -n "$CTX" ] && printf '%s\n' "$CTX"
  fi
elif [ -n "$OUT" ]; then
  printf '%s' "$OUT"
fi

exit $CODE
