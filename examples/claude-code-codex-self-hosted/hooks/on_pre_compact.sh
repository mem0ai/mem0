#!/usr/bin/env bash
# Hook: PostCompact (Claude Code) / PreCompact (Codex)
#
# Fires right before the session context is summarized and compacted — the
# last chance to persist what is about to be dropped from the window. This is
# the most valuable persistence point for a memory layer.
#
# Reads the tail of the session transcript and stores it via POST /memories.
# The self-hosted server runs its own LLM extraction (infer=true by default),
# so the hook stays dependency-free: no summarization logic in bash.
#
# Input:  JSON on stdin (session_id, transcript_path, cwd)
# Output: none (side effect: memory persistence)
#
# Must never block compaction: any failure exits 0 silently.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=mem0_env.sh
. "$SCRIPT_DIR/mem0_env.sh" 2>/dev/null || exit 0

if ! mem0_ready; then
  exit 0
fi

INPUT=$(cat)
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null || echo "")

if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  exit 0
fi

# Persist the last exchanges (tail) as one message so the server extracts
# facts/decisions from them. 12000 chars keeps the request small while still
# covering the most recent work.
TAIL=$(tail -c 12000 "$TRANSCRIPT_PATH" 2>/dev/null || echo "")

if [ -z "$TAIL" ]; then
  exit 0
fi

MEM0_SOURCE="pre_compact"
mem0_add "Session transcript excerpt to remember (extract durable facts, decisions, and preferences): ${TAIL}" \
  "{\"source\": \"${MEM0_SOURCE}\"}"

exit 0
