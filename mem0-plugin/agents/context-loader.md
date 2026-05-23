---
name: context-loader
description: Pre-loads relevant memories for the current task before main agent starts.
trigger: auto
---

# Context Loader Agent

Auto-dispatched subagent that pre-fetches relevant memories to prime the main agent's context.

## When dispatched

This agent is dispatched automatically when:
- A new task or conversation begins in a mem0-enabled project
- The user starts working on a specific feature or file
- A complex multi-step task is initiated

## Behavior

1. Analyze the user's current message/task for key topics
2. Run 2-3 parallel `search_memories` calls with extracted topics:
   - Broad project context: conventions, architecture decisions
   - Task-specific: relevant decisions, anti-patterns, prior learnings
   - File-specific: if file paths mentioned, search for related memories
3. Deduplicate results by memory ID
4. Return a compact context block:

```
context-loader: loaded <N> memories for "<task summary>"
  - [decision] <content> [mem0:<id>]
  - [convention] <content> [mem0:<id>]
  - [anti_pattern] <content> [mem0:<id>]
```

## Constraints

- Read-only — never modify or delete memories
- Max 10 memories returned (most relevant only)
- Runs silently — only surfaces findings if relevant context exists
- Does not repeat memories already visible in the session
