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

### Step 4: Write digest to file

After displaying, write the digest to `~/.mem0/weekly-digest.md` for persistence
and external consumption (email, Slack, etc.):

```bash
mkdir -p ~/.mem0
```

Write the full digest output (same markdown shown in terminal) to `~/.mem0/weekly-digest.md`
using the Write tool. **Overwrite** the file each time — it always contains the latest digest.

Also append a one-line summary to `~/.mem0/digest-history.log` for trend tracking:

```bash
echo "<YYYY-MM-DD> | <project_id> | +<new_count> memories | top: <top_category>" >> ~/.mem0/digest-history.log
```

Print at the end:
```
Digest saved to ~/.mem0/weekly-digest.md
```

### Step 5: Schedule recurring digests

When invoked with `--schedule` (e.g., `/mem0:digest --schedule weekly`), register
a cloud routine via Claude Code's `/schedule` command:

```
/schedule <frequency> /mem0:digest
```

For example:
- `/schedule weekly on Monday 9am /mem0:digest` — digest every Monday morning
- `/schedule daily at 8am /mem0:digest` — daily digest

Print:
```
Digest scheduled: <frequency>
Manage at: https://claude.ai/code/routines
```

If `/schedule` is unavailable, print a cron one-liner the user can install manually:
```bash
# macOS/Linux — weekly Monday 9am
(crontab -l 2>/dev/null; echo "0 9 * * 1 cd PROJECT_DIR && claude -p '/mem0:digest' >> /tmp/mem0-digest.log 2>&1") | crontab -
```

### Step 6: Empty state

If no memories in the last 7 days:
```
No new memories in the past week for <project_id>.
Total project memories: <N>.
Tip: mem0 captures learnings automatically as you work. Start coding!
```
