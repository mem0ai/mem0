---
name: stats
description: Displays memory usage statistics for the current session and project including counts by category, age distribution, and API latency. Use when checking how many memories exist, reviewing session activity, or auditing memory distribution across categories.
---

# Mem0 Stats

Show session and lifetime memory statistics.

## Execution

### Step 1: Gather session context

Read the session identity from env vars set by the plugin's shell.env hook:

- `MEM0_USER_ID` (falls back to `$USER` if unset)
- `MEM0_APP_ID` — the active project identifier
- `MEM0_SESSION_ID` — current session identifier
- `MEM0_BRANCH` — current git branch

If `MEM0_USER_ID` is unset, use `$USER`. If `MEM0_APP_ID` is unset, note "No project configured" and stop.

### Step 2: Fetch total memory count

Call `get_memories` MCP tool to get the total count for this project:

`filters={"AND": [{"user_id": "<MEM0_USER_ID>"}, {"app_id": "<MEM0_APP_ID>"}]}`, `page_size=1`

Read the `count` field from the response — this is the total number of memories for the project regardless of page size.

### Step 3: Fetch memories for category breakdown

Call `get_memories` MCP tool to retrieve memories for grouping:

`filters={"AND": [{"user_id": "<MEM0_USER_ID>"}, {"app_id": "<MEM0_APP_ID>"}]}`, `page_size=200`

Group each memory by:
1. `categories[0]` (platform-assigned) — primary grouping
2. `metadata.type` (agent-assigned) — secondary if `categories` is empty or absent
3. `created_at` date — for age analysis

**Category normalization:** Merge `auto_capture` and `uncategorized` into a single `uncategorized` row. Do NOT show `auto_capture` as its own row.

Also run a `search_memories` MCP tool call with `query="project"`, `filters={"AND": [{"user_id": "<MEM0_USER_ID>"}, {"app_id": "<MEM0_APP_ID>"}]}`, `top_k=1` to measure round-trip latency. Note the time before and after the MCP call — do NOT attempt raw HTTP calls to the API.

### Step 4: Display

Print a minimal plain-text dashboard. No markdown formatting — OpenCode TUI renders text verbatim.

Example output shape:

```
mem0 stats

Session  (<first 12 chars of MEM0_SESSION_ID>)  branch: main

Project: my-project  —  55 memories  —  API: 84ms

Category             Count
--------------------  -----
decision                24
convention              15
anti_pattern             6
task_learning            5
user_preference          3
session_state            2

Age  —  oldest: 2026-02-15  newest: 2026-05-23
  < 7 days: 5  |  7-30d: 12  |  30-90d: 10  |  > 90d: 8

Identity  —  user: kartik  project: my-project  branch: main
```

**Display rules:**
- Use plain text with spaces to align columns — no markdown tables, no | pipes, no ** bold, no ## headers
- Category section: sort by count descending, omit categories with 0 memories
- Age: single line with pipe-separated buckets, computed from `created_at`
- Session line: show MEM0_SESSION_ID (first 12 chars) and MEM0_BRANCH if available; skip the line entirely if both are unset
- If only 1-2 total memories, skip the category table — just show the count
- Keep everything compact — no decorative borders or filler

## Weekly digest mode

When invoked with `--weekly` (e.g., `/mem0:stats --weekly`), append a weekly
activity digest after the standard stats dashboard.

### W1: Fetch recent memories

Call `search_memories` in parallel with time-scoped queries:
1. `query="decisions made this week"`, `filters={"AND": [{"user_id": "<MEM0_USER_ID>"}, {"app_id": "<MEM0_APP_ID>"}, {"created_at": {"gte": "<7 days ago YYYY-MM-DD>"}}]}`, `top_k=20`
2. `query="bugs errors fixes"`, same time filter, `top_k=20`
3. `query="patterns conventions learnings"`, same time filter, `top_k=20`

### W2: Analyze

Merge by ID. Group into "New this week" by `categories[0]` or `metadata.type`.
Calculate: memories added last 7 days, most active categories, most active day.

### W3: Display

Append after the standard stats in plain text (no markdown):

```
This week (May 16 - May 23)

+12 memories  —  most active: Wednesday (5)

Category        New
--------------  ---
decision          5
task_learning     4
bug_fix           3

Highlights
- <2-3 sentence summary of most important decisions/learnings this week>
```

### W4: Write digest file

Write to `~/.mem0/weekly-digest.txt` (overwrite). Append one line to
`~/.mem0/digest-history.log`:
```
<YYYY-MM-DD> | <MEM0_APP_ID> | +<new_count> memories | top: <top_category>
```

### W5: Empty state

If no new memories in 7 days, output:
```
No new memories in the past week. Total: <N> memories in <MEM0_APP_ID>.
```

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
