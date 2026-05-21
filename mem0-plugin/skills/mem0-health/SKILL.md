---
name: mem0-health
description: >
  Diagnostic health check for the mem0 plugin. Verifies API key, MCP server
  connectivity, identity resolution, and memory read/write capability.
  TRIGGER: user runs /mem0:health, or asks "is mem0 working", "mem0 health",
  "check mem0 connection", "debug mem0".
---

# Mem0 Health Check

Run a diagnostic check on the mem0 plugin. Useful for troubleshooting.

## Execution

Run ALL checks, then display a single summary. Do not stop on the first failure.

### Check 1: API key

```bash
echo "${MEM0_API_KEY:-${CLAUDE_PLUGIN_OPTION_MEM0_API_KEY:-NOT_SET}}"
```

- If `NOT_SET`: FAIL — "No API key configured"
- If set: PASS — show first 6 chars + `...` (never print the full key)

### Check 2: Identity resolution

Read the active identity from the SessionStart banner or resolve manually:
- `user_id`: from `MEM0_RESOLVED_USER_ID` or `$USER`
- `project_id`: from `MEM0_PROJECT_ID` or current directory name
- `branch`: from `MEM0_BRANCH` or `git rev-parse --abbrev-ref HEAD`

PASS if all three are non-empty. WARN if any falls back to defaults.

### Check 3: MCP server connectivity

Call `search_memories` with:
- `query="health check"`, `user_id=<id>`, `limit=1`
- `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<project_id>"}]}`

- If returns successfully (even empty): PASS
- If errors: FAIL — show the error message

### Check 4: Memory write capability

Call `add_memory` with:
- `messages=[{"role": "user", "content": "Health check probe — safe to delete."}]`
- `user_id=<id>`, `app_id=<project_id>`
- `metadata={"type": "health_check", "probe": true}`

If it returns a memory ID: PASS — then immediately call `delete_memory` with that ID to clean up.
If it errors: FAIL — show the error.

### Check 5: Session stats tracker

```bash
SCRIPT_DIR="${CLAUDE_PLUGIN_ROOT:-${CODEX_PLUGIN_ROOT:-${CURSOR_PLUGIN_ROOT:-}}}/scripts"
python3 "$SCRIPT_DIR/session_stats.py" peek 2>/dev/null && echo "OK" || echo "FAIL"
```

### Display

```
## mem0 Health Check

| Check              | Status | Detail                        |
|--------------------|--------|-------------------------------|
| API Key            | PASS   | m0-dVe...                     |
| Identity           | PASS   | user=kartik, project=mem0     |
| MCP Connectivity   | PASS   | 142ms round-trip              |
| Memory Write/Read  | PASS   | write + delete OK             |
| Session Tracker    | PASS   | stats file active             |

All checks passed. mem0 is healthy.
```

If any check fails, add a `## Troubleshooting` section with specific fix steps for each failure.
