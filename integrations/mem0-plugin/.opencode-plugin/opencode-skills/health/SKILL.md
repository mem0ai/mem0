---
name: health
description: Diagnoses mem0 connectivity, API key validity, and memory read/write functionality. Use when memory operations fail, searches return empty, add_memory errors occur, or to verify the plugin is working correctly.
---

# Mem0 Health Check

Run a diagnostic check on the mem0 plugin. Useful for troubleshooting.

## Execution

Run ALL checks, then display a single summary. Do not stop on the first failure.

### Check 1: API key

```bash
_KEY="${MEM0_API_KEY:-}"
[ -n "$_KEY" ] && echo "${_KEY:0:6}..." || echo "NOT_SET"
```

- If `NOT_SET`: FAIL — "No API key configured"
- If set: PASS — the command already prints only the first 6 chars

### Check 2: Identity resolution

Resolve identity from environment variables set by the plugin's `shell.env` hook:

```bash
echo "user_id=${MEM0_USER_ID:-${USER:-}}"
echo "project_id=${MEM0_APP_ID:-}"
echo "branch=$(git branch --show-current 2>/dev/null || echo '')"
```

- `user_id`: from `MEM0_USER_ID`, falling back to `$USER`
- `project_id`: from `MEM0_APP_ID`
- `branch`: from `git branch --show-current`

PASS if all three are non-empty. WARN if any falls back to defaults.

### Check 3: Memory tool connectivity

Call `search_memories` with:
- `query="health check"`
- `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}]}`
- `top_k=1`

- If returns successfully (even empty): PASS
- If errors: FAIL — show the error message

### Check 4: Memory write capability

Call `add_memory` with:
- `text="Health check probe — safe to delete."`
- `user_id=<active_user_id>`
- `app_id=<active_project_id>`
- `metadata={"type": "health_check", "probe": true}`
- `infer=False`

The response returns `event_id` (v3 writes are async). Call `get_event_status(event_id=<event_id>)` to check processing.

- If status is `SUCCEEDED`: PASS — extract the memory ID from the event result, then call `delete_memory` with that ID to clean up.
- If status is `PENDING` after 5 seconds: PASS (write accepted, processing delayed)
- If errors: FAIL — show the error.

### Check 5: Session context

Check that the plugin's `shell.env` hook has injected session context into the environment:

```bash
echo "session_id=${MEM0_SESSION_ID:-}"
echo "app_id=${MEM0_APP_ID:-}"
echo "branch=${MEM0_BRANCH:-}"
```

- If all three are non-empty: PASS — "Session active"
- If any are missing: WARN — "Plugin env vars not set; shell.env hook may not have fired"

### Display

```
## mem0 health

PASS  API Key         m0-dVe...
PASS  Identity        user=kartik, project=mem0, branch=main
PASS  Memory Tools    142ms
PASS  Write/Read      write + delete OK
PASS  Session         session_id=abc123, app_id=mem0, branch=main

All checks passed.
```

If any check fails, add a `## Troubleshooting` section with specific fix steps for each failure.

## Extended mode: Memory Quality Analysis

When invoked with `--deep` (e.g., `/mem0:health --deep`), run the standard 5 checks above **plus** a memory quality scan.

### Quality Check 1: Duplicates

Call `get_memories` with `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}]}`, `page_size=200`. Compare all pairs within the same `metadata.type` group for high textual overlap (shared nouns/keywords > 60%). Report:

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

Duplicates: <N> · Stale: <N> · Contradictions: <N> · Orphans: <N>
```

If all counts are 0: `Memory quality: clean.`
If any non-zero: append `Run /mem0:dream to fix.`

To fix issues found by `--deep`, run `/mem0:dream` for automated consolidation (merges, prunes, conflict resolution).

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
