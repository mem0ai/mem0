#!/usr/bin/env bash
# Hook: SubagentStop
#
# Fires when a subagent finishes. Stdout is fed to parent agent
# as context, prompting it to capture reusable learnings.
#
# Input:  JSON on stdin with agent_type, result_summary
# Output: Text context for parent agent (exit 0)

set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

INPUT=$(cat)
AGENT_TYPE=$(echo "$INPUT" | jq -r '.agent_type // ""' 2>/dev/null || echo "")
RESULT_SUMMARY=$(echo "$INPUT" | jq -r '.result_summary // ""' 2>/dev/null || echo "")

# Skip short/empty results
if [ ${#RESULT_SUMMARY} -lt 50 ]; then
  exit 0
fi

# Read subagent skip list from config, default to Explore|Plan
_SKIP_CSV=$(python3 "$SCRIPT_DIR/parse_mem0_config.py" --key settings.subagent_skip "$(git rev-parse --show-toplevel 2>/dev/null || echo ".")" 2>/dev/null || echo "")
if [ -n "$_SKIP_CSV" ]; then
  _SKIP_PATTERN=$(echo "$_SKIP_CSV" | tr -d ' ' | tr ',' '|')
else
  _SKIP_PATTERN="Explore|Plan"
fi

# Skip read-only agents
if echo "$AGENT_TYPE" | grep -qE "^(${_SKIP_PATTERN})$" 2>/dev/null; then
  exit 0
fi

if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

echo "Subagent completed: ${AGENT_TYPE}. Reusable learnings from subagents are stored via add_memory."

exit 0
