---
name: memory-reviewer
description: Reviews stored memory quality by detecting duplicates, contradictions, and stale entries with actionable recommendations. Use when search results seem conflicting, before running dream consolidation, or for periodic memory hygiene audits.
---

# Memory Reviewer

Audits memory quality for the active project. Finds duplicates, contradictions, and low-confidence entries.

## When to use

- User asks "check my memories", "memory quality", "any duplicates?"
- User runs `/mem0:memory-reviewer` directly
- After a session with 5+ memory writes (suggest proactively)
- After `/mem0:health --deep` identifies issues

## Steps

1. **Fetch all memories** for active project via `get_memories` with `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}]}`, `page_size=200`. Paginate if needed — cap at 200 memories.

2. **Group by `metadata.type`**. Common types: `decision`, `convention`, `anti_pattern`, `task_learning`, `project_profile`, `user_preference`, `session_state`.

3. **Scan each group for issues:**

   | Issue | Detection method |
   |---|---|
   | **Near-duplicates** | >60% noun overlap within same type. Compare memory text after stripping stop words. |
   | **Contradictions** | Opposing facts about same topic (e.g., "use PostgreSQL" vs "use MySQL" for same component) |
   | **Low-confidence** | `metadata.confidence < 0.3` |
   | **Missing type** | No `metadata.type` set |
   | **Stale** | `created_at` older than 180 days with no updates |

4. **Output compact summary:**

```
memory-reviewer: project=<id> total=<N>
  duplicates:      <N> found
  contradictions:  <N> found
  low_confidence:  <N> found
  untagged:        <N> found
  stale:           <N> found
```

5. **If issues found**, list them with memory IDs:

```
Issues:
  [duplicate] "<memory_a>" ≈ "<memory_b>" [mem0:<id_a>, mem0:<id_b>]
  [contradiction] "<memory_x>" vs "<memory_y>" [mem0:<id_x>, mem0:<id_y>]
  [low_conf] "<memory_z>" (confidence: 0.1) [mem0:<id_z>]
```

6. **Suggest action**: "Run `/mem0:dream` to consolidate duplicates and resolve contradictions."

## Constraints

- **Read-only** — never modify or delete memories (that's `/mem0:dream`'s job)
- **Max 200 memories** per scan
- Report findings, let user decide on action

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
