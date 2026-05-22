# Source this file. Sets MEM0_API_KEY and MEM0_RESOLVED_USER_ID.
#
# API key resolution (first non-empty wins):
#   1. MEM0_API_KEY env var (explicit / shell profile)
#   2. CLAUDE_PLUGIN_OPTION_MEM0_API_KEY (set by Claude Code userConfig)
#
# User ID resolution:
#   1. MEM0_USER_ID env var (explicit override)
#   2. $USER, else "default"

# Resolve API key from userConfig fallback
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

# Also resolve project context
. "$( cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd )/_project.sh"
