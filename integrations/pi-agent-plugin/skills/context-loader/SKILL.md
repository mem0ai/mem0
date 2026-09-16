---
name: context-loader
description: Search earlier context when project history, decisions, or preferences could help with a specific question.
---

# Context Loader

Pre-fetches relevant memories to prime context before working on a task or topic.

## When to use

Use when earlier work could explain a decision, fix, command, or preference you
need. Skip this skill when the context already answers the question.

## Steps

1. **Extract topics** from current message/task. Identify: subject areas, people mentioned, project names, goal references.

2. **Search one focused question** using `mem0_memory` with `action="search"`. Keep the default project scope. Search again only if a specific gap remains.

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
