# Source this file. Sets MEM0_PROJECT_ID and MEM0_BRANCH.
#
# Resolution priority (project_id):
#   1. MEM0_PROJECT_ID env var (explicit override)
#   2. ~/.mem0/project_map.json lookup by $PWD (requires jq)
#   3. Git remote slug: strip protocol/prefix, strip .git, replace / and : with -
#      e.g. git@github.com:mem0ai/mem0.git -> mem0ai-mem0
#   4. Fallback: basename of $PWD
#
# Branch resolution:
#   git branch --show-current, fallback "unknown"

_mem0_resolve_project_id() {
  # 1. Explicit override
  if [ -n "${MEM0_PROJECT_ID:-}" ]; then
    printf '%s' "$MEM0_PROJECT_ID"
    return
  fi

  # 2. project_map.json lookup by $PWD
  _mem0_map="$HOME/.mem0/project_map.json"
  if [ -f "$_mem0_map" ] && command -v jq >/dev/null 2>&1; then
    _mem0_mapped=$(jq -r --arg cwd "$PWD" '.[$cwd] // empty' "$_mem0_map" 2>/dev/null)
    if [ -n "$_mem0_mapped" ]; then
      printf '%s' "$_mem0_mapped"
      return
    fi
  fi

  # 3. Git remote slug
  _mem0_remote_url=$(git remote get-url origin 2>/dev/null)
  if [ -n "$_mem0_remote_url" ]; then
    _mem0_slug="$_mem0_remote_url"
    # Strip .git suffix
    _mem0_slug="${_mem0_slug%.git}"
    # Strip protocol prefixes
    _mem0_slug="${_mem0_slug#https://}"
    _mem0_slug="${_mem0_slug#http://}"
    _mem0_slug="${_mem0_slug#ssh://}"
    _mem0_slug="${_mem0_slug#git://}"
    _mem0_slug="${_mem0_slug#git@}"
    # Replace first colon (SSH host:path separator) with /
    # shellcheck disable=SC2039
    _mem0_slug="${_mem0_slug/://}"
    # Keep only the last two path components (owner/repo)
    _mem0_owner=$(printf '%s' "$_mem0_slug" | awk -F'/' '{print $(NF-1)}')
    _mem0_repo=$(printf '%s' "$_mem0_slug" | awk -F'/' '{print $NF}')
    _mem0_slug="${_mem0_owner}-${_mem0_repo}"
    # Replace any remaining / and : with -
    # shellcheck disable=SC2039
    _mem0_slug="${_mem0_slug//\//-}"
    # shellcheck disable=SC2039
    _mem0_slug="${_mem0_slug//:/-}"
    if [ -n "$_mem0_slug" ]; then
      printf '%s' "$_mem0_slug"
      _MEM0_PERSIST_CWD="$PWD" _MEM0_PERSIST_SLUG="$_mem0_slug" python3 -c "
import os, sys
sys.path.insert(0, '$(dirname "${BASH_SOURCE[0]:-$0}")')
from _project import save_project_mapping
save_project_mapping(os.environ['_MEM0_PERSIST_CWD'], os.environ['_MEM0_PERSIST_SLUG'])
" 2>/dev/null || true
      return
    fi
  fi

  # 4. Fallback: basename of $PWD
  printf '%s' "$(basename "$PWD")"
}

_mem0_resolve_branch() {
  git branch --show-current 2>/dev/null || printf 'unknown'
}

MEM0_PROJECT_ID="$(_mem0_resolve_project_id)"
MEM0_BRANCH="$(_mem0_resolve_branch)"
export MEM0_PROJECT_ID
export MEM0_BRANCH
