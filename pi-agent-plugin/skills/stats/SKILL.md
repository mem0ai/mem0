---
name: stats
description: Displays memory usage statistics including counts by category, age distribution, and project summary. Use when checking how many memories exist, reviewing activity, or auditing memory distribution.
---

# Stats

Show memory statistics for the current project scope.

## Execution

### Step 1: Fetch all memories

Use `mem0_memory` tool with `action="get_all"` to fetch all memories for the current project.

### Step 2: Compute statistics

Group by:
1. `categories[0]` — primary grouping
2. `created_at` date — for age analysis

### Step 3: Display

Print a minimal dashboard:

```
## mem0 stats

**Project: my-project** — 55 memories

| Category         | Count |
|------------------|-------|
| preferences      |    18 |
| decisions        |    12 |
| goals            |     8 |
| lessons          |     7 |
| identity         |     5 |
| work             |     3 |
| technical        |     2 |

**Age** — oldest: 2026-02-15, newest: 2026-06-08
  < 7 days: 5 · 7-30d: 12 · 30-90d: 10 · > 90d: 8

**Identity** — user: kartik · project: my-project
```

**Display rules:**
- Category table: sort by count descending, omit categories with 0 memories
- Age: single line with dot-separated buckets, computed from `created_at`
- If only 1-2 total memories, skip the category table — just show the count
- Keep everything compact — no decorative borders

## Weekly digest mode

When invoked with `--weekly` (e.g., `/mem0-stats --weekly`), append a weekly activity digest:

### W1: Analyze recent memories

Use `mem0_memory` tool with `action="search"` for time-scoped queries:
1. `query="decisions goals this week"`
2. `query="lessons learned recently"`
3. `query="preferences habits"`

### W2: Display

```
### This week

+12 memories — most active: Wednesday (5)

| Category      | New |
|---------------|-----|
| decisions     |   5 |
| lessons       |   4 |
| goals         |   3 |

**Highlights**
- <2-3 sentence summary of most important new memories this week>
```

### W3: Empty state

If no new memories recently:
```
No new memories in the past week. Total: <N> memories.
```
