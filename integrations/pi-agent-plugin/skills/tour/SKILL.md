---
name: tour
description: Browses all stored memories grouped by category with full content display. Use when reviewing all memories, exploring stored knowledge, onboarding to a new session, or getting an overview of what the agent remembers.
---

# Memory Tour

Show the user what Mem0 has stored — a full walkthrough of all memories grouped by category.

## Cross-project mode

When invoked with `--all-projects` (e.g., `/mem0-tour --all-projects`), search across ALL projects:

1. Use `mem0_memory` tool with `action="get_all"`, `scope="global"` — no project filter.
2. Group results by project first, then by category within each project.
3. Display:
   ```
   ## <project_1> (<N> memories) <- current
   **Goals** — <memory content>
   ...

   ## <project_2> (<N> memories)
   ...

   <N> memories across <M> projects
   ```
4. Mark the current project with `<- current` in the heading.

If `--all-projects` is NOT present, use the standard single-project flow below.

## Search mode

When `/mem0-tour` receives a search query argument (e.g., `/mem0-tour cooking recipes`), run in **search mode** — compact one-liner results:

1. Use `mem0_memory` tool with `action="search"`, `query=<query>`.
2. Display compact results (same format as the search skill).
3. If no results: `No memories matching "<query>".`

If no query argument and no `--all-projects` flag, use the full tour flow below.

## Execution

### Step 1: Fetch ALL memories

Use `mem0_memory` tool with `action="get_all"`.

### Step 2: Group by category

Group memories using their `categories` field. Map to display names:

| Category | Display name |
|---|---|
| `identity` | Identity & Background |
| `preferences` | Preferences |
| `goals` | Goals & Aspirations |
| `projects` | Projects & Initiatives |
| `decisions` | Decisions |
| `technical` | Technical Knowledge |
| `relationships` | People & Relationships |
| `routines` | Routines & Workflows |
| `lessons` | Lessons Learned |
| `work` | Work & Professional |
| anything else | Other |

### Step 3: Display results

Sort groups by descending memory count. For each group:

```
## <display_name> (<count> memories)
- <full_memory_content> (<date>)
- ...
```

Show the **full memory text** for each entry — do NOT truncate. If a group has more than 10 entries, show top 10 by recency and note `... and <N> more`.

### Step 4: Print totals

```
<N> memories across <M> categories
```

### Step 5: Empty state

If zero memories found:
```
No memories stored yet. Start a conversation — Mem0 captures learnings automatically, or use /mem0-remember to store something manually.
```
