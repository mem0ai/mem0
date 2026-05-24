#!/usr/bin/env bash
set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_identity.sh"

INPUT=$(cat)
SOURCE=$(echo "$INPUT" | jq -r '.source // "startup"' 2>/dev/null || echo "startup")

if [ "$SOURCE" = "startup" ]; then
  python3 "$SCRIPT_DIR/session_stats.py" init 2>/dev/null || true
  rm -f /tmp/mem0_recent_reads_${USER}_* 2>/dev/null || true
fi
PYTHONPATH="$SCRIPT_DIR" python3 "$SCRIPT_DIR/load_settings.py" init 2>/dev/null || true
rm -f "/tmp/mem0_rubric_injected_${USER}" 2>/dev/null || true
rm -f /tmp/mem0_rubric_* 2>/dev/null || true
MEM0_SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""' 2>/dev/null || echo "")
if [ -z "$MEM0_SESSION_ID" ]; then
  MEM0_SESSION_ID="ses_$(date +%s)_$$"
fi
printf '%s' "$MEM0_SESSION_ID" > "/tmp/mem0_session_id_${USER}"
export MEM0_SESSION_ID

if [ -z "${MEM0_API_KEY:-}" ]; then
  cat <<BANNER
## Mem0 — Setup Required

\`user=${MEM0_RESOLVED_USER_ID:-$USER} | project=${MEM0_PROJECT_ID:-unknown} | branch=${MEM0_BRANCH:-unknown} | auth=none\`

IMPORTANT: In your FIRST response to the user, you MUST display the identity banner exactly as shown below (copy-paste it as your opening line before any other output):

\`\`\`
Mem0 — Setup Required | user=${MEM0_RESOLVED_USER_ID:-$USER} | project=${MEM0_PROJECT_ID:-unknown} | branch=${MEM0_BRANCH:-unknown} | auth=none
\`\`\`

MEM0_API_KEY is not set. You MUST run the \`mem0:onboard\` skill now using the Skill tool to set up the API key and configure mem0 for this project. Do not ask — just invoke it.
BANNER
  exit 0
fi

_DATA_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.mem0/plugin-data}"
if [ -f "${_DATA_DIR}/.install-failed" ]; then
  echo ""
  echo "mem0 SDK installation failed. Some features may not work."
  echo "Run: ${CLAUDE_PLUGIN_ROOT:-$SCRIPT_DIR/..}/scripts/ensure_deps.sh"
  echo ""
fi

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

cat <<BANNER
## Mem0 Active

\`user=$MEM0_RESOLVED_USER_ID${_MEM0_IDENTITY_ANNOTATION} | project=$MEM0_PROJECT_ID | branch=$MEM0_BRANCH | memories=$MEM0_COUNT | auth=api_key\`

IMPORTANT: In your FIRST response to the user, you MUST display the identity banner exactly as shown below (copy-paste it as your opening line before any other output):

\`\`\`
Mem0 Active | user=$MEM0_RESOLVED_USER_ID${_MEM0_IDENTITY_ANNOTATION} | project=$MEM0_PROJECT_ID | branch=$MEM0_BRANCH | memories=$MEM0_COUNT | auth=api_key
\`\`\`

Always include \`user_id\` + \`app_id\` in every \`search_memories\` filter and \`add_memory\` call:
- user_id: \`$MEM0_RESOLVED_USER_ID\`
- app_id: \`$MEM0_PROJECT_ID\` (project scope — passed as top-level \`app_id\`, NOT in metadata)

BANNER

MEM0_CWD_RESOLVED=$(echo "$INPUT" | jq -r '.cwd // "."' 2>/dev/null || echo ".")
if command -v python3 >/dev/null 2>&1; then
  MEM0_PROJECT_CONFIG=$(python3 "$SCRIPT_DIR/parse_mem0_config.py" --full "$MEM0_CWD_RESOLVED" 2>/dev/null || echo "{}")
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
fi

if [ "$SOURCE" = "startup" ]; then
  if [ "$MEM0_COUNT" = "0" ]; then
    cat <<'EOF'
This is a new project with 0 memories. You MUST invoke the `mem0:onboard` skill now using the Skill tool to import project files and install coding categories. Do not ask the user — just invoke it immediately before responding.
EOF
  else
    cat <<'EOF'
Search mem0 for recent decisions and task learnings before responding to the user's first message. Run 2 parallel searches: one for `decision` type, one for `task_learning` type.
EOF
  fi

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

python3 "$SCRIPT_DIR/telemetry.py" session_start --source="$SOURCE" --memory_count="${MEM0_COUNT:-0}" 2>/dev/null &

exit 0
