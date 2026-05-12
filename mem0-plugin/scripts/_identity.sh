# Source this file. Sets MEM0_RESOLVED_USER_ID.
#
# Resolution priority:
#   1. MEM0_USER_ID env var (explicit override)
#   2. ~/.mem0/identity.json cache (pinned to current MEM0_API_KEY fingerprint)
#   3. Derived: "mem0-" + sha256(MEM0_API_KEY)[:12]
#   4. Fallback: $USER, else "default"
#
# Same MEM0_API_KEY across machines yields the same user_id, which fixes
# the "47 user buckets per account" symptom from running on multiple
# laptops with different $USER values.

_mem0_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | cut -d' ' -f1
  else
    shasum -a 256 | cut -d' ' -f1
  fi
}

_mem0_resolve_identity() {
  if [ -n "${MEM0_USER_ID:-}" ]; then
    printf '%s' "$MEM0_USER_ID"
    return
  fi

  local api_key="${MEM0_API_KEY:-}"
  local cache="$HOME/.mem0/identity.json"

  if [ -n "$api_key" ]; then
    local digest
    digest=$(printf '%s' "$api_key" | _mem0_sha256)
    local fp="${digest:0:8}"

    if [ -f "$cache" ]; then
      local cached_fp cached_id
      cached_fp=$(jq -r '.api_key_fingerprint // ""' "$cache" 2>/dev/null)
      cached_id=$(jq -r '.user_id // ""' "$cache" 2>/dev/null)
      if [ "$cached_fp" = "$fp" ] && [ -n "$cached_id" ]; then
        printf '%s' "$cached_id"
        return
      fi
    fi

    local derived="mem0-${digest:0:12}"
    mkdir -p "$HOME/.mem0" 2>/dev/null && \
      printf '{"user_id":"%s","source":"api_key","api_key_fingerprint":"%s","resolved_at":"%s"}\n' \
        "$derived" "$fp" "$(date -u +%FT%TZ)" > "$cache" 2>/dev/null
    printf '%s' "$derived"
    return
  fi

  printf '%s' "${USER:-default}"
}

MEM0_RESOLVED_USER_ID="$(_mem0_resolve_identity)"
export MEM0_RESOLVED_USER_ID
