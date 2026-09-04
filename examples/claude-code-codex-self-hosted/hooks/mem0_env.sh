#!/usr/bin/env bash
# Shared environment + REST helpers for the self-hosted Mem0 hooks.
#
# Sources this file from every hook script. All values can be overridden
# through environment variables so a single setup works across projects.
#
# Required:
#   MEM0_API_KEY   API key created in the self-hosted dashboard (Settings -> API Keys)
# Optional:
#   MEM0_BASE_URL  Defaults to http://localhost:8888 (the self-hosted REST API)
#   MEM0_USER_ID   Defaults to "default"
#   MEM0_AGENT_ID  Defaults to "claude-code" or "codex" depending on MEM0_PLATFORM
#   MEM0_TOP_K     Defaults to 5
#   MEM0_THRESHOLD Defaults to 0.0 (no minimum similarity)

set -uo pipefail

MEM0_BASE_URL="${MEM0_BASE_URL:-http://localhost:8888}"
MEM0_USER_ID="${MEM0_USER_ID:-default}"
MEM0_PLATFORM="${MEM0_PLATFORM:-claude}"
if [ -z "${MEM0_AGENT_ID:-}" ]; then
  MEM0_AGENT_ID="default"
fi
MEM0_TOP_K="${MEM0_TOP_K:-5}"
MEM0_THRESHOLD="${MEM0_THRESHOLD:-0.0}"

# Fail open: if no API key is set, every helper becomes a no-op so a missing
# credential can never block or break a coding session.
mem0_ready() {
  [ -n "${MEM0_API_KEY:-}" ]
}

# POST /search  ->  search memories relevant to a query
# Usage: mem0_search "the query" [top_k]
mem0_search() {
  local query="$1"
  local top_k="${2:-$MEM0_TOP_K}"
  curl -sS --max-time 5 -X POST "${MEM0_BASE_URL}/search" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${MEM0_API_KEY}" \
    -d "{\"query\": $(jq -Rn --arg q "$query" '$q' 2>/dev/null || printf '"%s"' "$query"), \"filters\": {\"user_id\": \"${MEM0_USER_ID}\", \"agent_id\": \"${MEM0_AGENT_ID}\"}, \"top_k\": ${top_k}, \"threshold\": ${MEM0_THRESHOLD}}" \
    2>/dev/null || echo '{"results": []}'
}

# POST /memories  ->  store new memories extracted from a message
# Usage: mem0_add "the message content" [metadata_json]
mem0_add() {
  local content="$1"
  local metadata="${2:-}"
  if [ -z "$metadata" ]; then
    metadata='{}'
  fi
  curl -sS --max-time 10 -X POST "${MEM0_BASE_URL}/memories" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${MEM0_API_KEY}" \
    -d "{\"messages\": [{\"role\": \"user\", \"content\": $(jq -Rn --arg c "$content" '$c' 2>/dev/null || printf '"%s"' "$content")}], \"user_id\": \"${MEM0_USER_ID}\", \"agent_id\": \"${MEM0_AGENT_ID}\", \"metadata\": ${metadata}}" \
    2>/dev/null || echo '{"results": []}'
}

# Format search results as a compact, human-readable context block.
# Emits nothing when there are no results.
mem0_format_results() {
  local json="$1"
  jq -r '.results[]? | select(.score == null or .score >= '"${MEM0_THRESHOLD}"') | "- " + (.memory // .text // "")' <<<"$json" 2>/dev/null | sed '/^[[:space:]]*$/d'
}

# Emit context in the format expected by the calling platform.
# Claude Code expects hookSpecificOutput JSON; Codex appends stdout directly.
# Usage: mem0_emit_context "hookEventName" "context text"
mem0_emit_context() {
  local event="$1"
  local context="$2"
  if [ "${MEM0_PLATFORM}" = "codex" ]; then
    printf '%s\n' "${context}"
  else
    jq -cn --arg event "$event" --arg ctx "$context" \
      '{hookSpecificOutput: {hookEventName: $event, additionalContext: $ctx}}'
  fi
}
