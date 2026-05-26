#!/usr/bin/env bash
# PreToolUse hook for mem0 MCP tools.
# Injects identity (user_id, app_id) and metadata defaults when the agent
# omits them. Uses the hookSpecificOutput.updatedInput contract to modify
# tool call parameters before execution.
#
# Handles:
#   add_memory         — top-level user_id, app_id, metadata defaults
#   search_memories    — user_id/app_id into filters.AND[]
#   get_memories       — user_id/app_id into filters.AND[]
#   delete_all_memories — top-level user_id, app_id
#
# Hook contract:
#   exit 0 = allow. If stdout contains {"hookSpecificOutput": {"updatedInput": ...}},
#            the updatedInput replaces the tool's input parameters.
#   exit 2 = block (stderr shown as rejection reason).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/_identity.sh" 2>/dev/null || true

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)

# Determine which handler to use based on tool name
HANDLER=""
case "$TOOL_NAME" in
  mcp__mem0__add_memory|mcp__plugin_mem0_mem0__add_memory)
    HANDLER="add_memory" ;;
  mcp__mem0__search_memories|mcp__plugin_mem0_mem0__search_memories)
    HANDLER="search_memories" ;;
  mcp__mem0__get_memories|mcp__plugin_mem0_mem0__get_memories)
    HANDLER="get_memories" ;;
  mcp__mem0__delete_all_memories|mcp__plugin_mem0_mem0__delete_all_memories)
    HANDLER="delete_all" ;;
  *) exit 0 ;;
esac

TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input // "{}"' 2>/dev/null)

_PATCH_OUT="/tmp/mem0_enforce_$$"
_MEM0_TOOL_INPUT="$TOOL_INPUT" \
_MEM0_USER_ID="${MEM0_RESOLVED_USER_ID:-}" \
_MEM0_APP_ID="${MEM0_PROJECT_ID:-}" \
_MEM0_HANDLER="$HANDLER" \
python3 <<'PYEOF' > "$_PATCH_OUT" 2>/dev/null || true
import json, os, sys

raw = os.environ.get("_MEM0_TOOL_INPUT", "{}")
try:
    inp = json.loads(raw)
except Exception:
    sys.exit(0)

handler = os.environ.get("_MEM0_HANDLER", "")
resolved_uid = os.environ.get("_MEM0_USER_ID", "")
resolved_aid = os.environ.get("_MEM0_APP_ID", "")
changed = False


def inject_top_level_identity(inp, uid, aid):
    """Inject user_id/app_id as top-level params (for add_memory, delete_all)."""
    changed = False
    if uid and not inp.get("user_id"):
        inp["user_id"] = uid
        changed = True
    if aid and not inp.get("app_id"):
        inp["app_id"] = aid
        changed = True
    return changed


def inject_filter_identity(inp, uid, aid):
    """Inject user_id/app_id into filters.AND[] (for search/get_memories)."""
    changed = False
    if not uid and not aid:
        return False

    filters = inp.get("filters")

    if filters is None:
        # No filters at all — create from scratch
        and_clauses = []
        if uid:
            and_clauses.append({"user_id": uid})
        if aid:
            and_clauses.append({"app_id": aid})
        inp["filters"] = {"AND": and_clauses}
        return True

    if not isinstance(filters, dict):
        return False

    # Check if filters already contain user_id/app_id
    and_clauses = filters.get("AND")
    if and_clauses is None:
        # Filters exist but no AND — could be flat like {"user_id": "x"}
        has_uid = "user_id" in filters
        has_aid = "app_id" in filters
        if has_uid and has_aid:
            return False
        # Convert flat filters to AND format and add missing identity
        existing = []
        for k, v in list(filters.items()):
            existing.append({k: v})
        if uid and not has_uid:
            existing.append({"user_id": uid})
            changed = True
        if aid and not has_aid:
            existing.append({"app_id": aid})
            changed = True
        if changed:
            inp["filters"] = {"AND": existing}
        return changed

    if not isinstance(and_clauses, list):
        return False

    # AND array exists — check for existing user_id/app_id
    has_uid = any("user_id" in c for c in and_clauses if isinstance(c, dict))
    has_aid = any("app_id" in c for c in and_clauses if isinstance(c, dict))

    if uid and not has_uid:
        and_clauses.append({"user_id": uid})
        changed = True
    if aid and not has_aid:
        and_clauses.append({"app_id": aid})
        changed = True

    return changed


if handler == "add_memory":
    changed = inject_top_level_identity(inp, resolved_uid, resolved_aid)

    meta = inp.get("metadata") or {}

    if "confidence" not in meta:
        meta["confidence"] = 0.7
        changed = True
    if "files" not in meta:
        meta["files"] = ["*"]
        changed = True
    if "source" not in meta:
        meta["source"] = "auto_capture"
        changed = True
    if "type" not in meta:
        meta["type"] = "task_learning"
        changed = True

    if meta.get("confidence", 0) >= 1.0 and "infer" not in inp:
        inp["infer"] = False
        changed = True

    # Track session in metadata instead of run_id.
    # run_id creates a separate entity partition in the v3 API,
    # making memories invisible to search/get_memories calls
    # that don't include a run_id filter.
    if "session_id" not in meta:
        sid = os.environ.get("MEM0_SESSION_ID", "")
        if not sid:
            session_file = "/tmp/mem0_session_id_" + os.environ.get("USER", "default")
            if os.path.isfile(session_file):
                try:
                    with open(session_file) as f:
                        sid = f.read().strip()
                except OSError:
                    pass
        if sid:
            meta["session_id"] = sid
            changed = True

    if changed:
        inp["metadata"] = meta

elif handler in ("search_memories", "get_memories"):
    changed = inject_filter_identity(inp, resolved_uid, resolved_aid)
    # Re-read filters from inp (inject_filter_identity may have replaced the dict)
    filters = inp.get("filters") or {}
    and_clauses = filters.get("AND")
    if and_clauses is None:
        and_clauses = []
        filters["AND"] = and_clauses
        inp["filters"] = filters
    if isinstance(and_clauses, list):
        has_run_id = any("run_id" in c for c in and_clauses if isinstance(c, dict))
        if not has_run_id:
            and_clauses.append({"run_id": "*"})
            changed = True

elif handler == "delete_all":
    changed = inject_top_level_identity(inp, resolved_uid, resolved_aid)

if changed:
    print(json.dumps(inp))
PYEOF
PATCHED=$(cat "$_PATCH_OUT" 2>/dev/null)
rm -f "$_PATCH_OUT"

if [ -n "$PATCHED" ] && echo "$PATCHED" | jq empty 2>/dev/null; then
  jq -n --argjson updated "$PATCHED" '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "allow",
      "updatedInput": $updated
    }
  }' 2>/dev/null || true
fi

exit 0
