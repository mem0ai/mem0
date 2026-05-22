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

Check if the session stats file exists and is readable:

```bash
STATS_FILE="/tmp/mem0_session_stats_${USER}.json"
if [ -f "$STATS_FILE" ] && python3 -c "import json; json.load(open('$STATS_FILE'))" 2>/dev/null; then
  echo "OK"
else
  echo "FAIL"
fi
```

This file is created by the SessionStart hook and updated by PostToolUse hooks throughout the session. If it doesn't exist, the session hooks may not have fired yet — try sending a message first, then recheck.

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

## Extended mode: Memory Quality Analysis

When invoked with `--deep` (e.g., `/mem0:health --deep`) or `--fix` (e.g., `/mem0:health --fix`), run the standard 5 checks above **plus** a memory quality scan.

`--fix` implies `--deep` and automatically applies safe fixes after showing the analysis (see bottom of this section).

### Quality Check 1: Duplicates

Call `get_memories` with `user_id`, `app_id`, `page_size=200`. Compare all pairs within the same `metadata.type` group for high textual overlap (shared nouns/keywords > 60%). Report:

```
Potential duplicates: <N> pairs
  [mem0:<id1>] ≈ [mem0:<id2>] — both about "<shared topic>"
```

### Quality Check 2: Stale memories

Flag memories where:
- `metadata.type` is `session_state` or `compact_summary` AND older than 90 days
- `metadata.confidence` < 0.3 AND older than 30 days

```
Stale candidates: <N>
  [mem0:<id>] — session_state, 142d old
```

### Quality Check 2b: Low-confidence memories

Flag memories where `metadata.confidence` < 0.5 (regardless of age). Report separately from stale:

```
Low-confidence memories: <N>
  [mem0:<id>] — confidence=0.3, "<content preview>"
```

### Quality Check 3: Contradictions

Within each `metadata.type` group, flag pairs that assert opposing facts about the same topic. Use semantic judgment — look for negation patterns, conflicting tool/framework choices, or reversed decisions.

```
Possible contradictions: <N>
  [mem0:<idA>] vs [mem0:<idB>] — conflicting on "<topic>"
```

### Quality Check 4: Orphan memories

Memories with no `metadata.type` set, or with `metadata.type` not in the 17 known coding categories. These were likely written without proper tagging.

```
Untagged/orphan memories: <N>
```

### Quality summary

```
## Memory Quality
| Metric         | Count | Action                          |
|----------------|-------|---------------------------------|
| Duplicates     | <N>   | Run /mem0:dream to merge        |
| Stale          | <N>   | Run /mem0:dream to prune        |
| Contradictions | <N>   | Run /mem0:dream to resolve      |
| Orphans        | <N>   | Consider retagging via MCP      |
```

If all counts are 0: `Memory quality: clean. No duplicates, stale entries, or contradictions found.`

### Auto-fix mode (`--fix`)

When `--fix` is passed, apply these safe fixes automatically after displaying the quality summary:

1. **Orphans:** For each untagged memory, infer a `metadata.type` from content and call `update_memory` to set it. If inference is uncertain, skip.
2. **Stale `session_state`/`compact_summary` > 90d:** Delete them via `delete_memory`. These are ephemeral by design.
3. **Duplicates:** Do NOT auto-merge — print "Run `/mem0:dream` to merge duplicates" instead.
4. **Contradictions:** Do NOT auto-resolve — print "Run `/mem0:dream` to resolve contradictions" instead.
5. **Low-confidence < 0.3 AND > 30d old:** Delete them via `delete_memory`.

Print a summary of actions taken:

```
## Auto-fix Results
  Deleted: <N> stale, <N> low-confidence
  Retagged: <N> orphans
  Skipped: <N> duplicates (use /mem0:dream), <N> contradictions (use /mem0:dream)
```
