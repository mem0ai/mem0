#!/usr/bin/env bash
# Hook: SessionStart (matcher: startup|resume|compact)
#
# Bootstraps mem0 context at the start of every session.
# Output becomes part of Claude's context so it calls mem0 MCP tools.
#
# Input:  JSON on stdin with session_id, source, transcript_path, model, cwd
# Output: Text injected into Claude's context (exit 0)

# Intentionally omit -e so the script always outputs a bootstrap prompt
# even if jq is missing or stdin is malformed.
set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

# Skip the bootstrap entirely if no API key is configured -- the agent
# would otherwise be told to call mem0 MCP tools that will all fail.
if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_identity.sh
. "$SCRIPT_DIR/_identity.sh"

INPUT=$(cat)
SOURCE=$(echo "$INPUT" | jq -r '.source // "startup"' 2>/dev/null || echo "startup")

# Identity line is emitted before every bootstrap variant so the agent
# uses the same user_id the hooks resolved. Without this, the agent's
# search_memories/add_memory MCP calls may bind to a different bucket
# than what the hooks write to.
echo "## Mem0 Identity"
echo ""
echo "Active user_id: \`$MEM0_RESOLVED_USER_ID\`"
echo ""
echo "Always include \`{\"user_id\": \"$MEM0_RESOLVED_USER_ID\"}\` (wrapped in an \`AND\` clause) in every \`search_memories\` filter and as \`user_id\` on every \`add_memory\` call. This keeps the agent's MCP calls aligned with the bucket the hooks write to."
echo ""

if [ "$SOURCE" = "startup" ]; then
  cat <<'EOF'
## Mem0 Session Bootstrap

You have access to persistent memory via the mem0 MCP tools. Before doing anything else:

1. Call `search_memories` with a query related to the current project or user request to load relevant context.
2. Review the returned memories to understand what has been learned in prior sessions.
3. If appropriate, call `get_memories` to browse all stored memories for this user.

IMPORTANT: Do NOT skip this step. Always bootstrap context first.
EOF

elif [ "$SOURCE" = "resume" ]; then
  cat <<'EOF'
## Mem0 Session Resumed

This is a resumed session. Your prior context is already loaded. Before continuing:

1. Call `search_memories` with a query related to the current task to refresh relevant memories.
2. If significant time has passed, search for recent project-wide updates.

Continue where you left off.
EOF

elif [ "$SOURCE" = "compact" ]; then
  # Capture the just-generated compact summary in the background.
  # PreCompact fires too early to see this entry; SessionStart-compact
  # is the first place isCompactSummary=true is in the transcript.
  echo "$INPUT" | python3 "$SCRIPT_DIR/capture_compact_summary.py" 2>/dev/null &

  cat <<'EOF'
## Mem0 Post-Compaction Recovery

Context was just compacted. The Claude Code-generated compact summary
is being captured to mem0 in the background as `metadata.type=compact_summary`.

1. Call `search_memories` to reload context, layering up to three angles:
   - `metadata.type=session_state` -- the rich pre-compaction summary you wrote
   - `metadata.type=compact_summary` -- the platform-generated condensed summary just now
   - `metadata.type=decision` / `anti_pattern` -- specific facts you stored during the session
2. Continue working from the recovered context.
EOF
fi

exit 0
