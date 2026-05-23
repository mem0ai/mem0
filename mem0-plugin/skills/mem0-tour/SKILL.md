---
name: mem0-tour
description: Browse stored memories grouped by category
---

# Mem0 Project Tour

Show the user what mem0 has stored for the current project.

## Cross-project mode

When invoked with `--all-projects` (e.g., `/mem0:tour --all-projects` or
`/mem0:tour --all-projects auth middleware`), search across ALL projects:

1. Call `get_memories` with `user_id=<active_user_id>`, `page_size=200` — **no `app_id` filter**.
2. If a search query was also provided, run `search_memories` with `query=<query>`,
   `filters={"AND": [{"user_id": "<id>"}]}`, `limit=20` — again no `app_id`.
3. Group results by `app_id` first, then by category within each project.
4. Display:
   ```
   ## Cross-Project Tour for <user_id>

   ### <app_id_1> (<N> memories)
   #### Architecture Decisions
   - <memory content>
   ...

   ### <app_id_2> (<N> memories)
   ...

   ---
   Total: <N> memories across <M> projects
   ```
5. Mark the current project with `← (current)` in the heading.

If `--all-projects` is NOT present, use the standard single-project flow below.

## Peek mode (compact search)

When `/mem0:tour` receives a search query argument (e.g., `/mem0:tour auth middleware`)
WITHOUT `--all-projects`, run in **peek mode** — compact one-liner results:

1. Run 2 parallel `search_memories` calls:
   - Broad: `query=<query>`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}`, `limit=10`
   - Targeted: `query=<query>`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}, {"metadata": {"type": "decision"}}]}`, `limit=5`
2. Deduplicate by ID, display compact results:
   ```
   ## mem0 search: "<query>" (<N> results)

   1. [decision] Auth module uses JWT with RS256 keys (2025-05-15) [mem0:a3f8b2c1]
   2. [anti_pattern] Don't use symmetric HS256 — leaked in env (2025-05-10) [mem0:7e2d9f4a]
   3. [convention] All middleware in src/middleware/ (2025-05-08) [mem0:c4d5e6f7]
   ```
   Format: `<number>. [<type>] <content, 80 chars> (<date>) [mem0:<short_id>]`
3. If no results: `No memories matching "<query>" for project <project_id>.`

If no query argument and no `--all-projects` flag, use the full tour flow below.

## Execution

### Step 1: Fetch ALL memories for this project

Call `get_memories` with:
- `user_id=<active_user_id>`
- `app_id=<active_project_id>`

This returns every memory scoped to the project — no semantic filtering, no missed results.

If `get_memories` doesn't support `app_id` as a direct parameter, use:
- `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}`

Pass `page_size=100` (or the maximum allowed) to get a full picture.

### Step 2: Run supplementary semantic searches

In parallel, run these `search_memories` calls to get relevance-ranked results for key topics:

- `query="architecture decisions design choices"`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}`, `limit=10`
- `query="bugs errors failures anti-patterns"`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}`, `limit=10`
- `query="project setup tooling conventions preferences"`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}`, `limit=10`

**Do NOT filter by `metadata.type` in these calls.** The platform auto-assigns `categories` — filtering on `metadata.type` misses memories that were auto-categorized but don't have an explicit `metadata.type`.

### Step 3: Merge and group

Merge all results by memory ID (deduplicate). For each memory, determine its group using this priority:

1. **Platform `categories` field** (array on each memory, auto-assigned by Mem0). Use the first category value.
2. **`metadata.type` field** (if present, set explicitly by hooks/agent). Use as fallback if no `categories`.
3. **"other"** bucket for memories with neither.

Map category names to display names:

| Platform category / metadata.type | Display name |
|---|---|
| `architecture decisions`, `architecture_decisions`, `decision` | Architecture Decisions |
| `anti patterns`, `anti_patterns`, `anti_pattern` | Anti-Patterns |
| `task learnings`, `task_learnings`, `task_learning` | Task Learnings |
| `coding conventions`, `coding_conventions`, `convention` | Coding Conventions |
| `user preferences`, `user_preferences`, `user_preference` | User Preferences |
| `project profile`, `project_profile` | Project Profile |
| `tooling setup`, `tooling_setup`, `environmental` | Tooling & Setup |
| `technology`, `professional_details` | Tooling & Setup |
| `session_state` | Session State |
| `compact_summary` | Compact Summaries |
| anything else | Other |

### Step 4: Display results

For each group that has results, print:

```
## <display_name> (<count> memories)
- <full_memory_content> (score: <similarity_score_if_available>)
- ...
```

Show the **full memory text** for each entry — do NOT truncate. If a group has more than 10 entries, show top 10 by recency (or similarity score if from a search call) and note `... and <N> more`.

For groups with zero results, skip them entirely — don't print empty groups.

### Step 5: Print totals

```
---
Total: <N> unique memories across <M> categories for project <project_id>
Branch: <active_branch>
```

### Step 6: Empty state

If zero memories found for this project, print:
```
No memories stored yet for project <project_id>.
Run /mem0:onboard to import project files, or start working — mem0 captures learnings automatically.
```
