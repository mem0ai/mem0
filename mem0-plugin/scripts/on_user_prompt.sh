#!/usr/bin/env bash
# Hook: UserPromptSubmit
#
# Fires on every user message. Searches mem0 for relevant memories
# and injects them into Claude's context before processing.
#
# Input:  JSON on stdin with prompt, session_id, cwd, transcript_path
# Output: Matching memories as context text (exit 0)
#
# Skips search for very short prompts (< 20 chars) and when
# MEM0_API_KEY is not set. Uses a 3s timeout to minimize latency.

# Intentionally omit -e so the script always exits 0 even if
# curl or jq fail — must never block the user's prompt.
set -uo pipefail

INPUT=$(cat)
PROMPT=$(echo "$INPUT" | jq -r '.prompt // ""' 2>/dev/null || echo "")

# Skip trivial prompts — not worth a network call
if [ ${#PROMPT} -lt 20 ]; then
  exit 0
fi

API_KEY="${MEM0_API_KEY:-}"
if [ -z "$API_KEY" ]; then
  exit 0
fi

USER_ID="${MEM0_USER_ID:-${USER:-default}}"

# Build request body safely via jq to avoid injection
BODY=$(jq -n --arg query "$PROMPT" --arg user_id "$USER_ID" \
  '{query: $query, filters: {user_id: $user_id}, top_k: 5}')

# Search mem0 for memories relevant to this prompt
RESPONSE=$(curl -s --max-time 3 \
  -X POST "https://api.mem0.ai/v2/memories/search/" \
  -H "Authorization: Token $API_KEY" \
  -H "Content-Type: application/json" \
  -d "$BODY" \
  2>/dev/null || echo "")

if [ -z "$RESPONSE" ]; then
  exit 0
fi

# Extract memories from response (API returns a flat array)
MEMORIES=$(echo "$RESPONSE" | jq -r '
  if type == "array" then . else .results // [] end |
  if length == 0 then empty else
  "## Relevant memories from mem0\n\n" +
  (map(select(.memory != null) | "- " + .memory) | join("\n"))
  end
' 2>/dev/null || echo "")

if [ -n "$MEMORIES" ]; then
  echo "$MEMORIES"
fi

exit 0
