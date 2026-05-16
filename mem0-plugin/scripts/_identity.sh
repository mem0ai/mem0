# Source this file. Sets MEM0_RESOLVED_USER_ID.
#
# Resolution priority:
#   1. MEM0_USER_ID env var (explicit override)
#   2. $USER, else "default"

_mem0_resolve_identity() {
  if [ -n "${MEM0_USER_ID:-}" ]; then
    printf '%s' "$MEM0_USER_ID"
    return
  fi
  printf '%s' "${USER:-default}"
}

MEM0_RESOLVED_USER_ID="$(_mem0_resolve_identity)"
export MEM0_RESOLVED_USER_ID
