---
name: mem0-context-loader
description: Search memories from earlier OpenCode sessions in this repository. Use it when earlier work may already explain the code, error, decision, or command you need, so you can avoid repeating file reads, searches, or experiments.
---

# Context Loader

Pre-fetches relevant memories to prime context before working on a task.

## Steps

1. **Extract topics** from current message/task. Identify: file paths, module names, feature areas, error patterns.

2. **Call `search_memories` once** with a focused question about the task: `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}`, `top_k=10`.

3. **Output compact context block** (max 10 memories):

```
context-loader: loaded <N> memories for "<task summary>"
  - [decision] <content> [mem0:<short_id>]
  - [convention] <content> [mem0:<short_id>]
  - [anti_pattern] <content> [mem0:<short_id>]
```

4. If **zero results**: output nothing. Don't announce empty context.

## Constraints

- **Read-only** — never modify or delete memories
- **Max 10 memories** returned (most relevant only)
- **Silent on empty** — only surfaces findings if relevant context exists
- Skip memories already visible in current session context

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
