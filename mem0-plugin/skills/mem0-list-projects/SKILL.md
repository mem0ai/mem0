---
name: mem0-list-projects
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
## mem0 Projects for <user_id>

| Project | Memories | Last Active | Top Categories |
|---------|----------|-------------|---------------|
| <app_id_1> | <count> | <date> | decision, convention, anti_pattern |
| <app_id_2> | <count> | <date> | task_learning, environmental |
| ... | | | |

Active project: <current_project_id> ← (current)
Total: <N> projects, <M> total memories
```

Mark the current project with `← (current)`.

### Step 4: Empty state

If zero memories found:
```
No projects found for user <user_id>.
Run /mem0:onboard in a project directory to get started.
```

### Step 5: Suggest next actions

```
Switch project: /mem0:switch-project <name>
Browse memories: /mem0:tour
```
