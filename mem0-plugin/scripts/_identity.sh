# Source this file. Sets MEM0_API_KEY, MEM0_RESOLVED_USER_ID, and settings.
#
# API key resolution (first non-empty wins):
#   1. MEM0_API_KEY env var (explicit / shell profile)
#   2. CLAUDE_PLUGIN_OPTION_API_KEY (set by `claude plugin configure mem0`)
#   3. CLAUDE_PLUGIN_OPTION_MEM0_API_KEY (legacy userConfig)
#
# Settings: ~/.mem0/settings.json (user-editable, falls back to defaults)

_SCRIPT_DIR="$( cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd )"

# Resolve API key: env var > userConfig
if [ -z "${MEM0_API_KEY:-}" ] && [ -n "${CLAUDE_PLUGIN_OPTION_API_KEY:-}" ]; then
  MEM0_API_KEY="$CLAUDE_PLUGIN_OPTION_API_KEY"
  export MEM0_API_KEY
fi
if [ -z "${MEM0_API_KEY:-}" ] && [ -n "${CLAUDE_PLUGIN_OPTION_MEM0_API_KEY:-}" ]; then
  MEM0_API_KEY="$CLAUDE_PLUGIN_OPTION_MEM0_API_KEY"
  export MEM0_API_KEY
fi

_mem0_resolve_identity() {
  if [ -n "${MEM0_USER_ID:-}" ]; then
    printf '%s' "$MEM0_USER_ID"
    return
  fi
  printf '%s' "${USER:-default}"
}

MEM0_RESOLVED_USER_ID="$(_mem0_resolve_identity)"
export MEM0_RESOLVED_USER_ID

_MEM0_IDENTITY_ANNOTATION=""
if [ -n "${MEM0_USER_ID:-}" ] && [ "$MEM0_USER_ID" != "${USER:-default}" ]; then
  _MEM0_IDENTITY_ANNOTATION=" (override; default: ${USER:-default})"
fi
export _MEM0_IDENTITY_ANNOTATION

# Load settings from ~/.mem0/settings.json
if command -v python3 >/dev/null 2>&1; then
  _SETTINGS_JSON=$(PYTHONPATH="$_SCRIPT_DIR" python3 -c "from load_settings import load_settings; import json; print(json.dumps(load_settings()))" 2>/dev/null || echo "{}")
  MEM0_AUTO_SAVE=$(echo "$_SETTINGS_JSON" | python3 -c "import sys,json; print(str(json.load(sys.stdin).get('auto_save',True)).lower())" 2>/dev/null || echo "true")
  MEM0_AUTO_SEARCH=$(echo "$_SETTINGS_JSON" | python3 -c "import sys,json; print(str(json.load(sys.stdin).get('auto_search',True)).lower())" 2>/dev/null || echo "true")
  MEM0_SEARCH_LIMIT=$(echo "$_SETTINGS_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('search_limit',10))" 2>/dev/null || echo "10")
  MEM0_RETENTION_SESSION_DAYS=$(echo "$_SETTINGS_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('retention_session_days',90))" 2>/dev/null || echo "90")
  MEM0_CONFIDENCE_THRESHOLD=$(echo "$_SETTINGS_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('confidence_threshold',0.3))" 2>/dev/null || echo "0.3")
  MEM0_DEBUG=$(echo "$_SETTINGS_JSON" | python3 -c "import sys,json; print(str(json.load(sys.stdin).get('debug',False)).lower())" 2>/dev/null || echo "false")
else
  MEM0_AUTO_SAVE="true"
  MEM0_AUTO_SEARCH="true"
  MEM0_SEARCH_LIMIT="10"
  MEM0_RETENTION_SESSION_DAYS="90"
  MEM0_CONFIDENCE_THRESHOLD="0.3"
  MEM0_DEBUG="false"
fi
export MEM0_AUTO_SAVE MEM0_AUTO_SEARCH MEM0_SEARCH_LIMIT MEM0_RETENTION_SESSION_DAYS MEM0_CONFIDENCE_THRESHOLD MEM0_DEBUG

# Also resolve project context
. "$_SCRIPT_DIR/_project.sh"
