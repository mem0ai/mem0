#!/usr/bin/env bash
set -uo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

INPUT=$(cat)
SOURCE=$(echo "$INPUT" | jq -r '.source // "startup"' 2>/dev/null || echo "startup")

if [ "$SOURCE" = "startup" ]; then
  python3 "$SCRIPT_DIR/session_stats.py" init 2>/dev/null || true
  rm -f /tmp/mem0_recent_reads_${USER:-default}_* 2>/dev/null || true
fi
PYTHONPATH="$SCRIPT_DIR" python3 "$SCRIPT_DIR/load_settings.py" init 2>/dev/null || true
rm -f "/tmp/mem0_rubric_injected_${USER:-default}" 2>/dev/null || true
rm -f /tmp/mem0_rubric_* 2>/dev/null || true
rm -f "/tmp/mem0_msg_count_${USER:-default}" 2>/dev/null || true
MEM0_SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""' 2>/dev/null || echo "")
if [ -z "$MEM0_SESSION_ID" ]; then
  MEM0_SESSION_ID="ses_$(date +%s)_$$"
fi
printf '%s' "$MEM0_SESSION_ID" > "/tmp/mem0_session_id_${USER:-default}"
export MEM0_SESSION_ID

# Persist identity to Claude's env so Bash tool calls, MCP config, and other hooks see them
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export MEM0_SESSION_ID=\"$MEM0_SESSION_ID\"" >> "$CLAUDE_ENV_FILE"
  echo "export MEM0_RESOLVED_USER_ID=\"${MEM0_RESOLVED_USER_ID:-${USER:-default}}\"" >> "$CLAUDE_ENV_FILE"
  echo "export MEM0_PROJECT_ID=\"${MEM0_PROJECT_ID:-unknown}\"" >> "$CLAUDE_ENV_FILE"
  echo "export MEM0_BRANCH=\"${MEM0_BRANCH:-unknown}\"" >> "$CLAUDE_ENV_FILE"
  if [ -n "${MEM0_API_KEY:-}" ]; then
    echo "export MEM0_API_KEY=\"$MEM0_API_KEY\"" >> "$CLAUDE_ENV_FILE"
  fi
fi

if [ -z "${MEM0_API_KEY:-}" ]; then
  _UID="${MEM0_RESOLVED_USER_ID:-${USER:-default}}"
  _PID="${MEM0_PROJECT_ID:-unknown}"
  _BR="${MEM0_BRANCH:-unknown}"
  cat <<BANNER
## Mem0 — Setup Required

\`user=${_UID} | project=${_PID} | branch=${_BR} | auth=none\`

IMPORTANT: In your FIRST response, display this exact status line as your opening line:

\`\`\`
Mem0 — Setup Required | user=${_UID} | project=${_PID} | branch=${_BR} | auth=none
\`\`\`

MEM0_API_KEY is not set. To configure:
- **Reinstall the plugin**: Uninstall and reinstall — Claude Code will prompt for your API key during setup (stored securely in keychain)
- **Desktop app**: Click the environment dropdown next to the prompt box → hover over **Local** → click the **gear icon** → add \`MEM0_API_KEY=m0-...\`
- **CLI**: Add \`export MEM0_API_KEY=m0-...\` to your shell profile (~/.zshrc or ~/.bashrc)
- Get a key at https://app.mem0.ai/dashboard/api-keys

Then invoke the \`mem0:onboard\` skill to complete setup.
BANNER
  exit 0
fi

_DATA_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.mem0/plugin-data}"
_INSTALL_WARN=""
if [ -f "${_DATA_DIR}/.install-failed" ]; then
  _INSTALL_WARN="mem0 SDK installation failed. Run: ${CLAUDE_PLUGIN_ROOT:-$SCRIPT_DIR/..}/scripts/ensure_deps.sh"
fi

MEM0_COUNT="?"
if command -v python3 >/dev/null 2>&1; then
  MEM0_COUNT=$(python3 -c "
import json, os, urllib.request, urllib.error
api_key = os.environ.get('MEM0_API_KEY', '')
user_id = os.environ.get('MEM0_RESOLVED_USER_ID', 'default')
app_id = os.environ.get('MEM0_PROJECT_ID', '')
global_search = os.environ.get('MEM0_GLOBAL_SEARCH', 'false') == 'true'
api_base = os.environ.get('MEM0_API_BASE', '').rstrip('/')

def get_count(filters):
    if not api_base:
        return 0
    body = json.dumps({'filters': filters}).encode()
    req = urllib.request.Request(
        f'{api_base}/v3/memories/?page=1&page_size=1',
        headers={'Authorization': f'Token {api_key}', 'Content-Type': 'application/json'},
        data=body, method='POST',
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read())
        if isinstance(data, dict) and 'count' in data:
            return data['count']
        if isinstance(data, list):
            return len(data)
    return 0

try:
    if global_search:
        filters = {'OR': [{'user_id': '*'}]}
    else:
        filters = {'AND': [{'user_id': user_id}, {'app_id': app_id}]}
    total = get_count(filters)
    print(total)
except Exception:
    print('?')
" 2>/dev/null || echo "?")
fi

_UID="${MEM0_RESOLVED_USER_ID:-${USER:-default}}"
_ANN="${_MEM0_IDENTITY_ANNOTATION:-}"
_PID="${MEM0_PROJECT_ID:-unknown}"
_BR="${MEM0_BRANCH:-unknown}"
_GS="${MEM0_GLOBAL_SEARCH:-false}"

if [ "$_GS" = "true" ]; then
  _SCOPE_LABEL="scope=global"
  _SCOPE_INSTR="Global search is ON — searches return all memories across all users and projects. Writes still use user_id: \`${_UID}\`, app_id: \`${_PID}\`."
else
  _SCOPE_LABEL="project=${_PID}"
  _SCOPE_INSTR="Always include \`user_id\` + \`app_id\` in every \`search_memories\` filter and \`add_memory\` call:
- user_id: \`${_UID}\`
- app_id: \`${_PID}\` (project scope — passed as top-level \`app_id\`, NOT in metadata)"
fi

cat <<BANNER
## Mem0 Active

\`user=${_UID}${_ANN} | ${_SCOPE_LABEL} | branch=${_BR} | memories=${MEM0_COUNT}\`

IMPORTANT: In your FIRST response, display this exact status line as your opening line:

\`\`\`
Mem0 Active | user=${_UID}${_ANN} | ${_SCOPE_LABEL} | branch=${_BR} | memories=${MEM0_COUNT}
\`\`\`

${_SCOPE_INSTR}

After completing any task, decision, or meaningful exchange, proactively store learnings via \`add_memory\`. Do NOT wait until the session ends — store memories incrementally as work progresses. Focus on: decisions made, bugs fixed, patterns discovered, user preferences, or task outcomes. Aim for 1–3 memories per substantial interaction.

BANNER

if [ -n "$_INSTALL_WARN" ]; then
  echo "$_INSTALL_WARN"
fi

MEM0_CWD_RESOLVED=$(echo "$INPUT" | jq -r '.cwd // "."' 2>/dev/null || echo ".")
if command -v python3 >/dev/null 2>&1; then
  MEM0_PROJECT_CONFIG=$(python3 "$SCRIPT_DIR/parse_mem0_config.py" --full "$MEM0_CWD_RESOLVED" 2>/dev/null || echo "{}")
  if [ -n "$MEM0_PROJECT_CONFIG" ] && [ "$MEM0_PROJECT_CONFIG" != "{}" ]; then
    _CONFIG_KEYS=$(echo "$MEM0_PROJECT_CONFIG" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))" 2>/dev/null || echo "?")
    echo "mem0.md loaded (${_CONFIG_KEYS} sections configured)."
  fi
fi

if [ "$SOURCE" = "startup" ]; then
  if [ "$MEM0_COUNT" = "0" ]; then
    echo "New project with 0 memories. Invoke the mem0:onboard skill to import project files. Coding categories install automatically in the background."
  else
    echo "Search mem0 for recent decisions and task learnings before responding. Run 2 parallel searches: one for decision type, one for task_learning type."

    # Inject compact recent activity timeline (non-blocking, 5s timeout)
    # Use perl alarm as portable timeout (macOS lacks GNU timeout)
    # Gated by auto_search: Mode 3 ("never read without request") skips it.
    if [ "${MEM0_AUTO_SEARCH:-true}" != "false" ]; then
      _TIMELINE=$(MEM0_CWD="$MEM0_CWD_RESOLVED" perl -e 'alarm 5; exec @ARGV' python3 "$SCRIPT_DIR/session_timeline.py" 2>/dev/null || echo "")
      if [ -n "$_TIMELINE" ]; then
        echo ""
        echo "$_TIMELINE"
      fi
    fi
  fi

  _PROJ_KEY=$(printf '%s' "$MEM0_CWD_RESOLVED" | tr '/' '-')
  _MEMORY_MD="$HOME/.claude/projects/${_PROJ_KEY}/memory/MEMORY.md"
  if [ -f "$_MEMORY_MD" ] && [ -s "$_MEMORY_MD" ]; then
    echo "Native MEMORY.md detected at ${_MEMORY_MD}. Add autoMemoryEnabled:false to settings.json or run /mem0:import."
  fi

  MEM0_CWD="$MEM0_CWD_RESOLVED" \
    python3 "$SCRIPT_DIR/auto_import.py" 2>/dev/null &

  # Configure the coding-category taxonomy in the background (idempotent, never blocks).
  # Prefer the venv python since this path needs the mem0ai SDK.
  _VENV_PY="${CLAUDE_PLUGIN_DATA:-$HOME/.mem0/plugin-data}/venv/bin/python3"
  if [ -x "$_VENV_PY" ]; then
    MEM0_CWD="$MEM0_CWD_RESOLVED" "$_VENV_PY" "$SCRIPT_DIR/auto_setup_categories.py" 2>/dev/null &
  else
    MEM0_CWD="$MEM0_CWD_RESOLVED" python3 "$SCRIPT_DIR/auto_setup_categories.py" 2>/dev/null &
  fi

elif [ "$SOURCE" = "resume" ]; then
  echo "Session resumed. Search mem0 for session_state and decision memories to pick up where you left off. Run 2 parallel searches."

elif [ "$SOURCE" = "compact" ]; then
  echo "Context compacted. Search mem0 for session_state and decision memories to recover context. Run 2 parallel searches."
  if [ "${MEM0_AUTO_SAVE:-true}" != "false" ]; then
    printf '%s' "$INPUT" | python3 "$SCRIPT_DIR/capture_compact_summary.py" 2>/dev/null &
  fi
fi

python3 "$SCRIPT_DIR/telemetry.py" session_start --source="$SOURCE" --memory_count="${MEM0_COUNT:-0}" 2>/dev/null &

exit 0
