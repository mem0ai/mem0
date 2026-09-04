---
name: mem0-tour
description: Browses all stored memories grouped by category with full content display. Use when reviewing all project memories, exploring stored knowledge, onboarding to a project, or getting an overview of captured decisions, conventions, and learnings.
---

# Mem0 Project Tour

Show the user what mem0 has stored for the current project.

## Cross-project mode

When invoked with `--all-projects` (e.g., `/mem0-tour --all-projects` or
`/mem0-tour --all-projects auth middleware`), search across ALL projects:

1. Call `get_memories` with `filters={"AND": [{"user_id": "<active_user_id>"}]}`, `page_size=200` — **no `app_id` filter**.
2. If a search query was also provided, run `search_memories` with `query=<query>`,
   `filters={"AND": [{"user_id": "<active_user_id>"}]}`, `top_k=20` — again no `app_id`.
3. Group results by `app_id` first, then by category within each project.
4. Display:
   ```
   ## <app_id_1> (<N> memories) ← current
   **Architecture Decisions** — <memory content>
   ...

   ## <app_id_2> (<N> memories)
   ...

   <N> memories across <M> projects
   ```
5. Mark the current project with `← (current)` in the heading.

If `--all-projects` is NOT present, use the standard single-project flow below.

## Peek mode (compact search)

When `/mem0-tour` receives a search query argument (e.g., `/mem0-tour auth middleware`)
WITHOUT `--all-projects`, run in **peek mode** — compact one-liner results:

1. Run 2 parallel `search_memories` calls:
   - Broad: `query=<query>`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}`, `top_k=10`, `rerank=true`
   - Targeted: `query=<query>`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}, {"metadata": {"type": "decision"}}]}`, `top_k=5`, `rerank=true`
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

Call `get_memories` to fetch all memories for this project:

`filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}]}`, `page_size=100`

### Step 2: Run supplementary semantic searches

In parallel, run these `search_memories` calls to get relevance-ranked results for key topics:

- `query="architecture decisions design choices"`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}`, `top_k=10`, `rerank=true`
- `query="bugs errors failures anti-patterns"`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}`, `top_k=10`, `rerank=true`
- `query="project setup tooling conventions preferences"`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}`, `top_k=10`, `rerank=true`

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

Sort groups by descending memory count. Display in compact tabular format:

First show the category summary table:

```
mem0 tour

Session (ses_abc123)  branch: main
Project: my-project  -  349 memories

Category                   Count
-----------------------------------------
tooling_setup                119
bug_fixes                     78
architecture_decisions        32
task_learnings                14
...
```

Then for each category (sorted by count descending), show memories as numbered one-liners. Truncate each memory to 100 chars max:

```
tooling_setup (119)
  1. User requires that no git commit or push be performed without explicit permission... 
  2. OpenCode plugins are loaded from ~/.config/opencode/plugins/ for global installation...
  3. Assistant determined that the symlink method for loading the Mem0 plugin was failing...
  ... and 116 more

bug_fixes (78)
  1. Fixed getAll filter format from flat object to AND-wrapped array for mem0ai TS SDK v3...
  2. Root cause of user_id mismatch: plugin derived kartik.labhshetwar from git email...
  ... and 76 more
```

Show top 5 memories per category by recency. If a group has more than 5, note `... and <N> more`.

Skip empty groups entirely.

### Step 5: Print totals

```
<N> memories across <M> categories
project: <project_id>  branch: <active_branch>

Identity - user: <user_id>  project: <project_id>  branch: <branch>
```

### Step 6: Empty state

If zero memories found for this project, print:
```
No memories stored yet for project <project_id>.
Start working - mem0 captures learnings automatically, or use /mem0-remember to save something now.
```

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim - markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
