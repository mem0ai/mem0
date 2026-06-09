---
name: projects
description: Lists all projects with stored memories for the current user, showing memory counts and last activity dates. Use when checking which projects have memories, comparing memory distribution, or finding a specific project scope.
---

# List Projects

Show all known project scopes for the current user.

## Execution

### Step 1: Fetch memories to discover projects

There is no dedicated "list projects" API endpoint. Discover projects by fetching the user's memories across all scopes.

Use `mem0_memory` tool with `action="get_all"`, `scope="user"` — this fetches all memories for the user regardless of project.

### Step 2: Extract distinct projects

For each memory, determine project by its `app_id` field.

Group by resolved project name. For each project, count:
- Total memories
- Most recent `created_at` date
- Top 3 categories by frequency

### Step 3: Display

```
## mem0 projects

  <project_1>  <count> memories  (last: <date>) <- current
  <project_2>  <count> memories  (last: <date>)

<N> projects, <M> total memories
```

Mark current project with `<- current`. Sort by memory count descending.

### Step 4: Empty state

If zero memories found:
```
No projects found. Use /mem0-remember to start storing memories.
```
