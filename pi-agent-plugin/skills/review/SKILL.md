---
name: review
description: Reviews stored memory quality by detecting duplicates, contradictions, and stale entries with actionable recommendations. Use when search results seem conflicting, before running dream consolidation, or for periodic memory hygiene audits.
---

# Memory Reviewer

Audits memory quality for the current project. Finds duplicates, contradictions, and low-quality entries.

## When to use

- User asks "check my memories", "memory quality", "any duplicates?"
- User runs `/mem0-review` directly
- After a session with many memory writes (suggest proactively)
- After `/mem0-status --deep` identifies issues

## Steps

1. **Fetch all memories** using `mem0_memory` tool with `action="get_all"`. Cap at 200 memories.

2. **Group by category**. Common categories: `preferences`, `decisions`, `goals`, `lessons`, `identity`, `work`, `technical`, `projects`, `relationships`, `routines`.

3. **Scan each group for issues:**

   | Issue | Detection method |
   |---|---|
   | **Near-duplicates** | >60% noun overlap within same category. Compare memory text after stripping stop words. |
   | **Contradictions** | Opposing facts about same topic (e.g., "prefers tea" vs "always drinks coffee") |
   | **Vague entries** | Fewer than 5 meaningful words, no specific details |
   | **Stale** | `created_at` older than 180 days |

4. **Output compact summary:**

```
memory-reviewer: total=<N>
  duplicates:      <N> found
  contradictions:  <N> found
  vague:           <N> found
  stale:           <N> found
```

5. **If issues found**, list them with memory IDs:

```
Issues:
  [duplicate] "<memory_a>" ~ "<memory_b>" [mem0:<id_a>, mem0:<id_b>]
  [contradiction] "<memory_x>" vs "<memory_y>" [mem0:<id_x>, mem0:<id_y>]
  [vague] "<memory_z>" [mem0:<id_z>]
```

6. **Suggest action**: "Run `/mem0-dream` to consolidate duplicates and resolve contradictions."

## Constraints

- **Read-only** — never modify or delete memories (that's `/mem0-dream`'s job)
- **Max 200 memories** per scan
- Report findings, let user decide on action
