---
name: mem0-stats
description: >
  Show memory statistics for the current session and project lifetime.
  Combines local session counters with API-fetched totals.
  TRIGGER: user runs /mem0:stats, or asks "how many memories", "mem0 stats",
  "memory usage", "show memory count".
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

Skip any section with zero data.
