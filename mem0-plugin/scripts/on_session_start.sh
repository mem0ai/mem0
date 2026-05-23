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

# Initialize session stats tracker and settings file
python3 "$SCRIPT_DIR/session_stats.py" init 2>/dev/null || true
PYTHONPATH="$SCRIPT_DIR" python3 "$SCRIPT_DIR/load_settings.py" init 2>/dev/null || true
rm -f "/tmp/mem0_rubric_injected_${USER}" 2>/dev/null || true
rm -f /tmp/mem0_rubric_* 2>/dev/null || true
rm -f "/tmp/mem0_recent_reads_${USER}" 2>/dev/null || true

INPUT=$(cat)
SOURCE=$(echo "$INPUT" | jq -r '.source // "startup"' 2>/dev/null || echo "startup")

# Skip bootstrap if no API key — still show banner but with "no key" status.
if [ -z "${MEM0_API_KEY:-}" ]; then
  echo "## Mem0 Inactive"
  echo ""
  echo "\`user=${MEM0_RESOLVED_USER_ID:-$USER} | project=${MEM0_PROJECT_ID:-unknown} | branch=${MEM0_BRANCH:-unknown} | api_key=NOT_SET\`"
  echo ""
  echo "Display this status line in your first response:"
  echo ""
  echo '```'
  echo "Mem0 Inactive | user=${MEM0_RESOLVED_USER_ID:-$USER} | project=${MEM0_PROJECT_ID:-unknown} | branch=${MEM0_BRANCH:-unknown} | api_key=NOT_SET"
  echo '```'
  echo ""
  echo "Set MEM0_API_KEY to enable persistent memory. Get a key at https://app.mem0.ai/dashboard/api-keys"
  exit 0
fi

# Check for failed dependency installation and warn the user
_DATA_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.mem0/plugin-data}"
if [ -f "${_DATA_DIR}/.install-failed" ]; then
  echo ""
  echo "⚠️ mem0 SDK installation failed. Some features may not work."
  echo "Run: ${CLAUDE_PLUGIN_ROOT:-$SCRIPT_DIR/..}/scripts/ensure_deps.sh"
  echo ""
fi

# Fetch project-scoped memory count (best-effort, don't block on failure, 5s timeout)
MEM0_COUNT="?"
if command -v python3 >/dev/null 2>&1; then
  MEM0_COUNT=$(python3 -c "
import json, os, urllib.request, urllib.error
api_key = os.environ.get('MEM0_API_KEY', '')
user_id = os.environ.get('MEM0_RESOLVED_USER_ID', 'default')
app_id = os.environ.get('MEM0_PROJECT_ID', '')
body = json.dumps({'filters': {'user_id': user_id, 'app_id': app_id}}).encode()
req = urllib.request.Request(
    'https://api.mem0.ai/v3/memories/?page=1&page_size=1',
    headers={'Authorization': f'Token {api_key}', 'Content-Type': 'application/json'},
    data=body,
    method='POST',
)
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read())
        if isinstance(data, dict) and 'count' in data:
            print(data['count'])
        elif isinstance(data, list):
            print(len(data))
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
echo "Display this status line in your first response:"
echo ""
echo '```'
echo "Mem0 Active | user=$MEM0_RESOLVED_USER_ID | project=$MEM0_PROJECT_ID | branch=$MEM0_BRANCH | memories=$MEM0_COUNT"
echo '```'
echo ""
echo "Use \`user_id=$MEM0_RESOLVED_USER_ID\` and \`app_id=$MEM0_PROJECT_ID\` in all mem0 MCP calls."
echo ""

# Load mem0.md project config if present (best-effort, non-blocking)
MEM0_PROJECT_CONFIG=""
MEM0_CWD_RESOLVED=$(echo "$INPUT" | jq -r '.cwd // "."' 2>/dev/null || echo ".")
if command -v python3 >/dev/null 2>&1; then
  MEM0_PROJECT_CONFIG=$(python3 "$SCRIPT_DIR/parse_mem0_config.py" --full "$MEM0_CWD_RESOLVED" 2>/dev/null || echo "{}")
fi
if [ -n "$MEM0_PROJECT_CONFIG" ] && [ "$MEM0_PROJECT_CONFIG" != "{}" ]; then
  _CONFIG_KEYS=$(echo "$MEM0_PROJECT_CONFIG" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))" 2>/dev/null || echo "?")
  echo "### Project Config (mem0.md)"
  echo "\`mem0.md loaded (${_CONFIG_KEYS} sections configured)\`"
  if [ -n "${MEM0_DEBUG:-}" ]; then
    echo "\`\`\`json"
    echo "$MEM0_PROJECT_CONFIG"
    echo "\`\`\`"
  fi
  echo ""
fi

if [ "$SOURCE" = "startup" ]; then
  # First-run detection: auto-trigger onboarding for new projects
  _SAFE_PID=$(printf '%s' "$MEM0_PROJECT_ID" | tr '/:' '--')
  _ONBOARD_MARKER="$HOME/.mem0/.onboarded_${_SAFE_PID}"
  if [ ! -f "$_ONBOARD_MARKER" ]; then
    mkdir -p "$HOME/.mem0" 2>/dev/null || true
    touch "$_ONBOARD_MARKER"
    cat <<'EOF'
First run for this project. Run `/mem0:onboard` now to import project files and install categories.
EOF
  else
    cat <<'EOF'
Search mem0 for recent decisions and task learnings before responding to the user's first message. Run 2 parallel searches: one for `decision` type, one for `task_learning` type.
EOF
  fi

  # Detect native Claude Code auto-memory for THIS project
  _PROJ_KEY=$(printf '%s' "$MEM0_CWD_RESOLVED" | tr '/' '-')
  _MEMORY_MD="$HOME/.claude/projects/${_PROJ_KEY}/memory/MEMORY.md"
  if [ -f "$_MEMORY_MD" ] && [ -s "$_MEMORY_MD" ]; then
    cat <<MEMEOF

### Native auto-memory detected

Found \`$_MEMORY_MD\`. The mem0 plugin handles all memory storage.
To avoid two parallel memory systems:
- Add \`"autoMemoryEnabled": false\` to \`~/.claude/settings.json\`
- Or run \`/mem0:import\` to migrate existing MEMORY.md content into mem0

MEMEOF
  fi

  # Auto-import declarative project files in background
  MEM0_CWD="$(echo "$INPUT" | jq -r '.cwd // "."' 2>/dev/null || echo ".")" \
    python3 "$SCRIPT_DIR/auto_import.py" 2>/dev/null &

elif [ "$SOURCE" = "resume" ]; then
  cat <<'EOF'
Session resumed. Search mem0 for `session_state` and `decision` memories to pick up where you left off. Run 2 parallel searches.
EOF

elif [ "$SOURCE" = "compact" ]; then
  cat <<'EOF'
Context compacted. Search mem0 for `session_state` and `decision` memories to recover context. Run 2 parallel searches.
EOF
fi

# Telemetry (background, fire-and-forget)
python3 "$SCRIPT_DIR/telemetry.py" session_start --source="$SOURCE" --memory_count="${MEM0_COUNT:-0}" 2>/dev/null &

exit 0
