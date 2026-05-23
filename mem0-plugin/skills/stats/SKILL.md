---
name: stats
description: Show memory usage stats for this session and project
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

### Step 2: Fetch lifetime stats from API

Call `get_memories` with:
- `user_id=<active_user_id>`
- `app_id=<active_project_id>`
- `page_size=100`

Count the returned memories. Group them by:
1. `categories[0]` (platform-assigned) — primary grouping
2. `metadata.type` (agent-assigned) — secondary if no categories
3. `created_at` date — for age analysis

Also run a `search_memories` call with `query="project"`, `limit=1` to measure round-trip latency (time the call).

### Step 3: Display

Print a compact dashboard with an ASCII histogram for category distribution:

```
## mem0 Stats

### This Session
  Memories written:  <N>
  Searches run:      <N>
  Categories touched: <list>

### Project Lifetime (<project_id>)
  Total memories:    <N>

  By category:
    decision          ████████████████ 24
    convention        ██████████░░░░░░ 15
    anti_pattern      ████░░░░░░░░░░░░  6
    task_learning     ███░░░░░░░░░░░░░  5
    user_preference   ██░░░░░░░░░░░░░░  3
    session_state     █░░░░░░░░░░░░░░░  2

  By age:
    < 7 days          ████████████████  5
    7–30 days         ██████████░░░░░░ 12
    30–90 days        ████░░░░░░░░░░░░ 10
    > 90 days         ██░░░░░░░░░░░░░░  8

  By access count:
    Never accessed    ████████████████ 18
    1–5 accesses      ████████░░░░░░░░ 10
    6–20 accesses     ████░░░░░░░░░░░░  4
    20+ accesses      █░░░░░░░░░░░░░░░  3

  Oldest memory:     <date>
  Newest memory:     <date>

### Health
  API latency:       <N>ms
  User:              <user_id>
  Project:           <project_id>
  Branch:            <branch>
```

**Histogram rules:**
- Max bar width: 16 characters. Scale all bars relative to the highest count.
- Use `█` for filled and `░` for empty. Right-align the count number.
- Sort categories by count descending. Omit categories with 0 memories.
- If only 1-2 categories exist, still show the histogram — it provides visual context.
- **Age buckets:** Compute from `created_at`. Buckets: <7d, 7–30d, 30–90d, >90d.
- **Access count buckets:** Read `metadata.access_count` (default 0 if absent). Buckets: 0, 1–5, 6–20, 20+.

Skip any section with zero data.

## Weekly digest mode

When invoked with `--weekly` (e.g., `/mem0:stats --weekly`), append a weekly
activity digest after the standard stats dashboard:

### W1: Fetch recent memories

Call `search_memories` in parallel with time-scoped queries:
1. `query="decisions made this week"`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}, {"created_at": {"gte": "<7 days ago YYYY-MM-DD>"}}]}`, `limit=20`
2. `query="bugs errors fixes"`, same time filter, `limit=20`
3. `query="patterns conventions learnings"`, same time filter, `limit=20`

### W2: Analyze

Merge by ID. Group into "New this week" by `categories[0]` or `metadata.type`.
Calculate: memories added last 7 days, most active categories, most active day.

### W3: Display

Append after the standard stats:

```
### Weekly Digest (<start_date> to <today>)

New Memories This Week: <N>
  <category>: <count>
    - <memory summary, 80 chars> (<date>)
    - ...

Activity Pattern
  Most active day: <day> (<N> memories)
  Categories touched: <list>

Highlights
  <2-3 sentence summary of most important decisions/learnings this week>
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
No new memories in the past week for <project_id>.
Total project memories: <N>.
```
