---
name: status
description: Diagnoses Mem0 connectivity, API key validity, and memory read/write functionality. Use when memory operations fail, searches return empty, or to verify the plugin is working correctly.
---

# Health Check / Status

Run a diagnostic check on the Mem0 plugin. Useful for troubleshooting.

## Execution

Run ALL checks, then display a single summary. Do not stop on the first failure.

### Check 1: API key

Verify the API key is configured. The plugin loads it from `MEM0_API_KEY` env var or `~/.pi/agent/mem0-config.json`.

- If not set: FAIL — "No API key configured"
- If set: PASS — show first 6 chars followed by `...`

### Check 2: Identity resolution

Report the resolved identity:
- `user_id`: from config, env, or system user
- `project_id`: auto-detected from current directory
- `session_id`: current session identifier

PASS if user_id and project_id are non-empty. WARN if any falls back to defaults.

### Check 3: Connectivity

Use `mem0_memory` tool with `action="search"`, `query="health check"`.

- If returns successfully (even empty): PASS
- If errors: FAIL — show the error message

### Check 4: Memory write capability

Use `mem0_memory` tool with `action="add"`, `content="Health check probe — safe to delete."`.

- If succeeds: PASS — then clean up by deleting the probe memory.
- If errors: FAIL — show the error.

### Display

```
## mem0 health

PASS  API Key          m0-dVe...
PASS  Identity         user=kartik, project=my-app, session=abc123
PASS  Connectivity     142ms
PASS  Write/Read       write + delete OK

All checks passed.
```

If any check fails, add a `## Troubleshooting` section with specific fix steps.

## Extended mode: Memory Quality Analysis

When invoked with `--deep` (e.g., `/mem0-status --deep`), run the standard checks above **plus** a memory quality scan.

### Quality Check 1: Duplicates

Fetch all memories with `mem0_memory` `action="get_all"`. Compare pairs within the same category for high textual overlap (shared nouns > 60%). Report:

```
Potential duplicates: <N> pairs
  [mem0:<id1>] ~ [mem0:<id2>] — both about "<shared topic>"
```

### Quality Check 2: Stale memories

Flag memories older than 180 days that haven't been accessed recently.

### Quality Check 3: Contradictions

Within each category, flag pairs that assert opposing facts.

### Quality summary

```
## Memory Quality

Duplicates: <N> · Stale: <N> · Contradictions: <N>
```

If all counts are 0: `Memory quality: clean.`
If any non-zero: append `Run /mem0-dream to fix.`
