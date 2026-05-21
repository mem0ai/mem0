---
name: mem0-digest
description: >
  Summarize recent memory activity for the current project. Shows new memories,
  categories touched, and growth trends over the past 7 days.
  TRIGGER: user runs /mem0:digest, or asks "weekly summary", "what's new in memory",
  "mem0 digest", "memory recap".
---

# Mem0 Weekly Digest

Summarize recent memory activity for the current project.

## Execution

### Step 1: Fetch recent memories

Call `search_memories` in parallel with different time-scoped queries:

1. `query="decisions made this week"`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}, {"created_at": {"gte": "<7 days ago YYYY-MM-DD>"}}]}`, `limit=20`
2. `query="bugs errors fixes"`, same time filter, `limit=20`
3. `query="patterns conventions learnings"`, same time filter, `limit=20`

Also call `get_memories` with `user_id` + `app_id` to get the full count for comparison.

### Step 2: Deduplicate and analyze

Merge results by memory ID. For each memory, extract:
- `created_at` date
- `categories[0]` or `metadata.type`
- First 100 chars of content

Group into:
- **New this week** (created in last 7 days)
- **Older** (created before, but surfaced by search)

Calculate:
- Total memories in project
- Memories added in last 7 days
- Most active categories this week
- Days with most activity

### Step 3: Display

```
## mem0 Weekly Digest — <project_id>
Period: <start_date> to <today>

### New Memories This Week: <N>
<category>: <count>
  - <memory summary, 80 chars> (<date>)
  - ...
<category>: <count>
  - ...

### Activity Pattern
Most active day: <day> (<N> memories)
Categories touched: <list>

### Project Totals
Total memories: <N> (up <N> from last week)
Top categories: <top 3 by count>

### Highlights
<2-3 sentence summary of the most important decisions, learnings, or patterns stored this week>
```

### Step 4: Empty state

If no memories in the last 7 days:
```
No new memories in the past week for <project_id>.
Total project memories: <N>.
Tip: mem0 captures learnings automatically as you work. Start coding!
```
