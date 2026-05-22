#!/usr/bin/env bash
# Hook: PostToolUseFailure (matcher: mcp__mem0__)
#
# Fires when a mem0 MCP tool call fails. Logs the failure, bumps telemetry,
# and injects a retry hint so Claude can recover.
#
# Input:  JSON on stdin with tool_name, tool_input, tool_error
# Output: Context injected into Claude's next response (exit 0)

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")
TOOL_RESULT=$(echo "$INPUT" | jq -r '.tool_error // ""' 2>/dev/null || echo "")
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}' 2>/dev/null || echo "{}")

# Extract the short tool name (strip mcp__mem0__ prefix)
SHORT_NAME="${TOOL_NAME#mcp__mem0__}"

# Log failure to persistent file for debugging
mkdir -p "$HOME/.mem0" 2>/dev/null || true
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) FAIL $TOOL_NAME: $TOOL_RESULT" >> "$HOME/.mem0/tool-failures.log" 2>/dev/null || true

# Telemetry (background, fire-and-forget)
python3 "$SCRIPT_DIR/telemetry.py" tool_failure --tool="$SHORT_NAME" 2>/dev/null &

# Classify the error
IS_AUTH_ERROR=""
IS_RATE_LIMIT=""
IS_NETWORK_ERROR=""

if echo "$TOOL_RESULT" | grep -qiE '(401|403|unauthorized|forbidden|invalid.*token|invalid.*key)'; then
  IS_AUTH_ERROR="true"
elif echo "$TOOL_RESULT" | grep -qiE '(429|rate.?limit|too many requests|quota)'; then
  IS_RATE_LIMIT="true"
elif echo "$TOOL_RESULT" | grep -qiE '(timeout|connect|ECONNREFUSED|network|DNS|resolve)'; then
  IS_NETWORK_ERROR="true"
fi

cat <<EOF

## mem0 tool failure: \`$SHORT_NAME\`

**Error:** $TOOL_RESULT
**Input:** \`$TOOL_INPUT\`

EOF

if [ -n "$IS_AUTH_ERROR" ]; then
  cat <<'EOF'
**Cause:** Authentication failure. MEM0_API_KEY may be invalid or expired.
**Action:** Tell the user their API key needs to be checked. Get a new key at https://app.mem0.ai/dashboard/api-keys
Do NOT retry — it will fail again with the same key.
EOF
elif [ -n "$IS_RATE_LIMIT" ]; then
  cat <<'EOF'
**Cause:** Rate limit hit.
**Action:** Wait a few seconds, then retry the same call. If it fails again, reduce the number of parallel mem0 calls.
EOF
elif [ -n "$IS_NETWORK_ERROR" ]; then
  cat <<'EOF'
**Cause:** Network connectivity issue reaching mem0 API.
**Action:** Retry once. If it fails again, inform the user and continue without memory context.
EOF
else
  cat <<EOF
**Action:** Retry the \`$SHORT_NAME\` call once. If it fails again, continue without memory context and inform the user.
EOF
fi

exit 0
