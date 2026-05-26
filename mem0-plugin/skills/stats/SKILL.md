---
name: stats
description: Displays memory usage statistics for the current session and project including counts by category, age distribution, and API latency. Use when checking how many memories exist, reviewing session activity, or auditing memory distribution across categories.
---

# Mem0 Stats

Show session and lifetime memory statistics.

## Execution

### Step 1: Gather session stats

Run the session stats reporter:

```bash
SCRIPT_DIR="${CLAUDE_PLUGIN_ROOT:-${CODEX_PLUGIN_ROOT:-${CURSOR_PLUGIN_ROOT:-}}}/scripts"
python3 "$SCRIPT_DIR/session_stats.py" peek 2>/dev/null || echo "{}"
```

The `peek` command returns JSON without clearing the stats file (unlike `report`).

If the script returns empty or errors, note "No session data available" and continue.

### Step 2: Fetch lifetime and session stats from API

**Lifetime stats:**
Call `get_memories` to fetch all memories for this project:

`filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}]}`, `page_size=100`

Group by:
1. `categories[0]` (platform-assigned) — primary grouping
2. `metadata.type` (agent-assigned) — secondary if no categories
3. `created_at` date — for age analysis

**Session stats (API-backed):**
Read the session ID file at `/tmp/mem0_session_id_$USER`. If it exists and contains
a non-empty value, also call `get_memories` with:
- `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}, {"run_id": "<session_id>"}]}`
- `page_size=100`

Additionally check for session memories stored without run_id (via metadata):
- `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}, {"metadata": {"session_id": "<session_id>"}}]}`
- `page_size=100`

Merge both session result sets by ID. This count represents memories written in the
current session. Cross-check with the local stats file — use the higher count.

Also run a `search_memories` MCP tool call with `query="project"`, `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}]}`, `top_k=1` to measure round-trip latency. Note the time before and after the MCP call — do NOT attempt raw HTTP calls to the API.

### Step 3: Display

Print a minimal dashboard. No ASCII bar charts — use a clean table layout:

```
## mem0 stats

**Session** (<session_id, first 12 chars>) — 3 written, 5 searches, categories: decision, convention

**Project: my-project** — 55 memories, API: 84ms

| Category             | Count |
|----------------------|-------|
| decision             |    24 |
| convention           |    15 |
| anti_pattern         |     6 |
| task_learning        |     5 |
| user_preference      |     3 |
| session_state        |     2 |

**Age** — oldest: 2026-02-15, newest: 2026-05-23
  < 7 days: 5 · 7–30d: 12 · 30–90d: 10 · > 90d: 8

**Identity** — user: kartik · project: my-project · branch: main
```

**Display rules:**
- Category table: sort by count descending, omit categories with 0 memories
- Age: single line with dot-separated buckets, computed from `created_at`
- Session line: skip if no session data available
- If only 1-2 total memories, skip the category table — just show the count
- Keep everything compact — no decorative borders or filler

## Weekly digest mode

When invoked with `--weekly` (e.g., `/mem0:stats --weekly`), append a weekly
activity digest after the standard stats dashboard:

### W1: Fetch recent memories

Call `search_memories` in parallel with time-scoped queries:
1. `query="decisions made this week"`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}, {"created_at": {"gte": "<7 days ago YYYY-MM-DD>"}}]}`, `top_k=20`
2. `query="bugs errors fixes"`, same time filter, `top_k=20`
3. `query="patterns conventions learnings"`, same time filter, `top_k=20`

### W2: Analyze

Merge by ID. Group into "New this week" by `categories[0]` or `metadata.type`.
Calculate: memories added last 7 days, most active categories, most active day.

### W3: Display

Append after the standard stats:

```
### This week (May 16 – May 23)

+12 memories — most active: Wednesday (5)

| Category      | New |
|---------------|-----|
| decision      |   5 |
| task_learning |   4 |
| bug_fix       |   3 |

**Highlights**
- <2-3 sentence summary of most important decisions/learnings this week>
```

### W4: Write digest file

Write to `~/.mem0/weekly-digest.md` (overwrite). Append one-line to
`~/.mem0/digest-history.log`:
```
<YYYY-MM-DD> | <project_id> | +<new_count> memories | top: <top_category>
```

### W5: Empty state

If no new memories in 7 days:
```
No new memories in the past week. Total: <N> memories in <project_id>.
```
