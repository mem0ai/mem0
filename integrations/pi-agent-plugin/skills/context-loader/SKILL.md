---
name: context-loader
description: Search memories from earlier Pi sessions in this repository. Use it when earlier work may already explain the code, error, decision, or command you need, so you can avoid repeating file reads, searches, or experiments.
---

# Context Loader

Pre-fetches relevant memories to prime context before working on a task or topic.

## Steps

1. **Extract topics** from current message/task. Identify: subject areas, people mentioned, project names, goal references.

2. **Call `mem0_memory` once** with `action="search"` and a focused question about the task.

3. **Output compact context block** (max 10 memories):

```
context-loader: loaded <N> memories for "<task summary>"
  - [decisions] <content> [mem0:<short_id>]
  - [preferences] <content> [mem0:<short_id>]
  - [lessons] <content> [mem0:<short_id>]
```

4. If **zero results**: output nothing. Don't announce empty context.

## Constraints

- **Read-only** — never modify or delete memories
- **Max 10 memories** returned (most relevant only)
- **Silent on empty** — only surfaces findings if relevant context exists
- Skip memories already visible in current session context
