---
name: context-loader
description: Searches and injects relevant memories into context before starting work on a task or topic. Use when beginning a new task, switching context, or when past decisions, preferences, or knowledge need to be loaded.
---

# Context Loader

Pre-fetches relevant memories to prime context before working on a task or topic.

## When to use

- Session start (auto-triggered by the extension's `before_agent_start` event)
- User starts work on a specific topic or area
- User says "what do we know about X" or "context for X"

## Steps

1. **Extract topics** from current message/task. Identify: subject areas, people mentioned, project names, goal references.

2. **Run 2-4 parallel searches** using `mem0_memory` tool with `action="search"` and different query angles:

   | Query angle | Purpose |
   |---|---|
   | Topic/subject name | Relevant decisions and preferences |
   | People mentioned | Relationship context |
   | Project/goal references | Progress and background |
   | Broad context | Catch-all for anything relevant |

3. **Deduplicate** results by memory ID across all search responses.

4. **Output compact context block** (max 10 memories):

```
context-loader: loaded <N> memories for "<task summary>"
  - [decisions] <content> [mem0:<short_id>]
  - [preferences] <content> [mem0:<short_id>]
  - [lessons] <content> [mem0:<short_id>]
```

5. If **zero results**: output nothing. Don't announce empty context.

## Constraints

- **Read-only** — never modify or delete memories
- **Max 10 memories** returned (most relevant only)
- **Silent on empty** — only surfaces findings if relevant context exists
- Skip memories already visible in current session context
