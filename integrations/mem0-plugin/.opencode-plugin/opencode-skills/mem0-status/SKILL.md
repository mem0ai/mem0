---
name: mem0-status
description: Diagnoses mem0 connectivity, API key validity, and memory read/write functionality. Use when memory operations fail, searches return empty, add_memory errors occur, or to verify the plugin is working correctly.
---

# Mem0 Status

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

Resolve identity from the `MEM0_*` environment variables set by the plugin's `shell.env` hook. These are the exact values the plugin uses to scope memories, so report them directly. Do NOT re-run `git` here: the plugin already resolved branch and project from git at session start, and re-shelling git can disagree with it — e.g. it prints an empty branch that renders as `(not a git repo)` while the Session check below shows `branch=main`. One source of truth keeps the two lines consistent.

```bash
echo "user_id=${MEM0_USER_ID:-${USER:-default}}"
echo "project_id=${MEM0_APP_ID:-}"
echo "branch=${MEM0_BRANCH:-main}"
_S="$HOME/.mem0/settings.json"
_SCOPE="$(grep -o '"default_scope"[[:space:]]*:[[:space:]]*"[a-z]*"' "$_S" 2>/dev/null | grep -o '[a-z]*"$' | tr -d '"')"
echo "default_scope=${_SCOPE:-project}"
```

- `user_id`: from `MEM0_USER_ID`, falling back to `$USER`
- `project_id`: from `MEM0_APP_ID`
- `branch`: from `MEM0_BRANCH` (the plugin's resolved value; falls back to `main` outside a git repo)
- `default_scope`: from `~/.mem0/settings.json` (`default_scope`), falling back to `project`. This is the scope memory tools use when none is given; change it with `/mem0-scope`.

PASS if `user_id` and `project_id` are non-empty. WARN if `project_id` is empty — the `shell.env` hook may not have fired (restart OpenCode). Report the branch verbatim from `MEM0_BRANCH`; never invent a string like `(not a git repo)`.

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

### Check 6: Auto-dream readiness

Explain whether auto-dream (memory consolidation) is eligible to run, and if not, exactly which gate is blocking. Auto-dream runs at most once per session and only when **all** gates pass: time since last consolidation ≥ `minHours`, sessions since ≥ `minSessions`, and project memory count ≥ `minMemories`.

Read the gate state and thresholds:

```bash
_ST="$HOME/.mem0/mem0-dream-state.json"
_SET="$HOME/.mem0/settings.json"
echo "sessions_since=$(grep -o '"sessionsSince"[[:space:]]*:[[:space:]]*[0-9]*' "$_ST" 2>/dev/null | grep -o '[0-9]*$' || echo 0)"
echo "last_consolidated_ms=$(grep -o '"lastConsolidatedAt"[[:space:]]*:[[:space:]]*[0-9]*' "$_ST" 2>/dev/null | grep -o '[0-9]*$' || echo 0)"
echo "min_hours=$(grep -o '"minHours"[[:space:]]*:[[:space:]]*[0-9]*' "$_SET" 2>/dev/null | grep -o '[0-9]*$' || echo 24)"
echo "min_sessions=$(grep -o '"minSessions"[[:space:]]*:[[:space:]]*[0-9]*' "$_SET" 2>/dev/null | grep -o '[0-9]*$' || echo 5)"
echo "min_memories=$(grep -o '"minMemories"[[:space:]]*:[[:space:]]*[0-9]*' "$_SET" 2>/dev/null | grep -o '[0-9]*$' || echo 20)"
echo "now_s=$(date +%s)"
echo "dream_env=${MEM0_DREAM:-unset}"
```

For the memory count, reuse the project memory count from Check 3/4 (or call `get_memories` with the project filter, `page_size=1`, and read `count`).

Compute each gate:
- **time**: `hours_since = (now_s - last_consolidated_ms/1000) / 3600`. Passes when `≥ min_hours`. If `last_consolidated_ms` is 0 it has never run → time gate passes.
- **sessions**: passes when `sessions_since ≥ min_sessions`.
- **memories**: passes when project memory count `≥ min_memories`.

Report:
- If `dream_env` is `false`/`0`/`no`/`off`, or `dream.enabled` is false in settings: WARN — "Auto-dream disabled".
- If all three gates pass: PASS — "eligible (runs at next session start)".
- Otherwise: WARN — list the blocking gate(s), e.g. `sessions 2/5, memories 3/20`. This is expected, not an error — auto-dream is just waiting. Note the user can run `/mem0-dream` to consolidate now, or lower the thresholds via the `dream` block in `~/.mem0/settings.json`.

### Display

```
## mem0 status

PASS  API Key         m0-dVe...
PASS  Identity        user=kartik, project=mem0, branch=main
PASS  Default scope   project
PASS  Memory Tools    142ms
PASS  Write/Read      write + delete OK
PASS  Session         session_id=abc123, app_id=mem0, branch=main
WARN  Auto-dream      waiting — sessions 2/5, memories 3/20 (/mem0-dream to run now)

All checks passed.
```

The Auto-dream line is informational: WARN here means "waiting on gates", not a failure. Show PASS when eligible, or "disabled" when turned off.

If any check fails, add a `## Troubleshooting` section with specific fix steps for each failure.

## Extended mode: Memory Quality Analysis

When invoked with `--deep` (e.g., `/mem0-status --deep`), run the standard 6 checks above **plus** a memory quality scan.

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
If any non-zero: append `Run /mem0-dream to fix.`

To fix issues found by `--deep`, run `/mem0-dream` for automated consolidation (merges, prunes, conflict resolution).

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
