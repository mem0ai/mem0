---
name: mem0-tour
description: >
  Show what mem0 knows about the current project. Dumps top memories
  grouped by category. Power-user-friendly proof of value.
  TRIGGER: user runs /mem0:tour, or asks "what do you know about this project",
  "show me my memories", "what has mem0 stored".
---

# Mem0 Project Tour

Show the user what mem0 has stored for the current project.

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
- <memory_content_truncated_to_120_chars> (score: <similarity_score_if_available>)
- ...
```

Show up to 5 memories per group. If a group has more than 5, show top 5 by recency (or similarity score if from a search call) and note `... and <N> more`.

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
