---
name: list-projects
description: List all projects that have stored memories
---

# Mem0 List Projects

Show all known project scopes for the current user.

## Execution

### Step 1: Fetch memories to discover app_ids

There is no dedicated "list projects" API endpoint. Discover projects by fetching
the user's memories and extracting distinct `app_id` values.

Call `get_memories` with:
- `filters={"user_id": "<active_user_id>"}`
- `page_size=200`

Do NOT pass `app_id` — we want memories across ALL projects.

If the response indicates more pages, paginate until all are fetched (up to 1000
memories max to avoid excessive API calls).

### Step 2: Extract distinct projects

For each memory, read the `app_id` field (may also appear as `metadata.app_id`
on older memories). Collect distinct values.

For each project, count:
- Total memories
- Most recent `created_at` date
- Top 3 `metadata.type` values by frequency

### Step 3: Display

```
## mem0 projects

  <app_id_1>  <count> memories  (last: <date>) ← current
  <app_id_2>  <count> memories  (last: <date>)

<N> projects, <M> total memories
```

Mark current project with `← current`. Sort by memory count descending.

### Step 4: Empty state

If zero memories found:
```
No projects found. Run /mem0:onboard to get started.
```
