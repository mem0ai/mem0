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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_identity.sh
. "$SCRIPT_DIR/_identity.sh"

# Skip the bootstrap entirely if no API key is configured -- the agent
# would otherwise be told to call mem0 MCP tools that will all fail.
if [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

# Initialize session stats tracker
python3 "$SCRIPT_DIR/session_stats.py" init 2>/dev/null || true

INPUT=$(cat)
SOURCE=$(echo "$INPUT" | jq -r '.source // "startup"' 2>/dev/null || echo "startup")

# Fetch project-scoped memory count (best-effort, don't block on failure, 5s timeout)
MEM0_COUNT="?"
if command -v python3 >/dev/null 2>&1; then
  MEM0_COUNT=$(python3 -c "
import json, os, urllib.request, urllib.error
api_key = os.environ.get('MEM0_API_KEY', '')
user_id = os.environ.get('MEM0_RESOLVED_USER_ID', 'default')
app_id = os.environ.get('MEM0_PROJECT_ID', '')
body = json.dumps({
    'query': 'project context',
    'user_id': user_id,
    'filters': {'AND': [{'user_id': user_id}, {'app_id': app_id}]},
    'limit': 100,
}).encode()
req = urllib.request.Request(
    'https://api.mem0.ai/v2/memories/search/',
    data=body,
    headers={'Authorization': f'Token {api_key}', 'Content-Type': 'application/json'},
    method='POST',
)
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        results = json.loads(r.read())
        if isinstance(results, list):
            n = len(results)
            print(f'{n}+' if n >= 100 else str(n))
        else:
            print('?')
except Exception:
    print('?')
" 2>/dev/null || echo "?")
fi

# Identity line is emitted before every bootstrap variant so the agent
# uses the same user_id the hooks resolved. Without this, the agent's
# search_memories/add_memory MCP calls may bind to a different bucket
# than what the hooks write to.
echo "## Mem0 Active"
echo ""
echo "\`user=$MEM0_RESOLVED_USER_ID | project=$MEM0_PROJECT_ID | branch=$MEM0_BRANCH | memories=$MEM0_COUNT\`"
echo ""
echo "Always include \`user_id\` + \`app_id\` in every \`search_memories\` filter and \`add_memory\` call:"
echo "- user_id: \`$MEM0_RESOLVED_USER_ID\`"
echo "- app_id: \`$MEM0_PROJECT_ID\` (project scope — passed as top-level \`app_id\`, NOT in metadata)"
echo ""

if [ "$SOURCE" = "startup" ]; then
  # First-run detection: auto-trigger onboarding for new projects
  _SAFE_PID=$(printf '%s' "$MEM0_PROJECT_ID" | tr '/:' '--')
  _ONBOARD_MARKER="$HOME/.mem0/.onboarded_${_SAFE_PID}"
  if [ ! -f "$_ONBOARD_MARKER" ]; then
    cat <<'EOF'
## Mem0 First Run — Automatic Onboarding

This is the first time mem0 is running for this project. You MUST run the onboarding wizard NOW before doing anything else.

Execute the `/mem0:onboard` skill immediately. This will:
1. Verify the API key
2. Detect and import project files (CLAUDE.md, AGENTS.md, .cursorrules, etc.)
3. Install coding categories optimized for development
4. Show a summary of what was set up

Do NOT skip this. Do NOT ask the user if they want to onboard. Just run `/mem0:onboard` now.
EOF
  else
    cat <<'EOF'
## Mem0 Session Bootstrap

You have access to persistent memory via the mem0 MCP tools. Before doing anything else:

1. Call `search_memories` with a query related to the current project or user request to load relevant context.
2. Review the returned memories to understand what has been learned in prior sessions.
3. If appropriate, call `get_memories` to browse all stored memories for this user.

IMPORTANT: Do NOT skip this step. Always bootstrap context first.
EOF
  fi

  # Auto-import declarative project files in background
  MEM0_CWD="$(echo "$INPUT" | jq -r '.cwd // "."' 2>/dev/null || echo ".")" \
    python3 "$SCRIPT_DIR/auto_import.py" 2>/dev/null &

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
