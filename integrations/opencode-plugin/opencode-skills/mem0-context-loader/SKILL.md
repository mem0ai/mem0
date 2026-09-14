---
name: mem0-context-loader
description: Searches and injects relevant memories into context before starting work on a task. Use when beginning a new task, switching context, or when project history, past decisions, or coding conventions need to be loaded.
---

# Context Loader

Pre-fetches relevant memories to prime context before working on a task.

## When to use

- Session start (invoke manually or auto-triggered by skill description matching)
- User starts work on a specific feature or file set
- Complex multi-step task begins
- User says "what do we know about X" or "context for X"

## Steps

1. **Extract topics** from current message/task. Identify: file paths, module names, feature areas, error patterns.

2. **Run 2-4 parallel `search_memories` calls** with different angles:

   | Query angle | Filter | Purpose |
   |---|---|---|
   | Feature/module name | `{"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}, {"metadata": {"type": "decision"}}]}` | Architecture decisions |
   | File paths mentioned | `{"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}, {"metadata": {"type": "convention"}}]}` | Coding patterns |
   | Error keywords (if any) | `{"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}, {"metadata": {"type": "anti_pattern"}}]}` | Known pitfalls |
   | Broad project context | `{"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}` | Catch-all |

3. **Deduplicate** results by memory ID across all search responses.

4. **Output compact context block** (max 10 memories):

```
context-loader: loaded <N> memories for "<task summary>"
  - [decision] <content> [mem0:<short_id>]
  - [convention] <content> [mem0:<short_id>]
  - [anti_pattern] <content> [mem0:<short_id>]
```

5. If **zero results**: output nothing. Don't announce empty context.

## Constraints

- **Read-only** — never modify or delete memories
- **Max 10 memories** returned (most relevant only)
- **Silent on empty** — only surfaces findings if relevant context exists
- Skip memories already visible in current session context

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
