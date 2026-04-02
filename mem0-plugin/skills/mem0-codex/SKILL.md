---
name: mem0-codex
description: >
  Mem0 persistent memory integration for Codex. Automatically retrieve relevant
  memories at the start of each task, store key learnings when tasks complete,
  and capture session state before context is lost. Use the mem0 MCP tools
  (add_memory, search_memories, get_memories, etc.) for all memory operations.
---

# Mem0 Memory Protocol for Codex

You have access to persistent memory via the mem0 MCP tools. Follow this protocol to maintain context across sessions.

## On every new task

1. Call `search_memories` with a query related to the current task or project to load relevant context.
2. Review returned memories to understand what has been learned in prior sessions.
3. If appropriate, call `get_memories` to browse all stored memories for this user.

## After completing significant work

Extract key learnings and store them using the `add_memory` tool:

- **Decisions made** -> Include metadata `{"type": "decision"}`
- **Strategies that worked** -> Include metadata `{"type": "task_learning"}`
- **Failed approaches** -> Include metadata `{"type": "anti_pattern"}`
- **User preferences observed** -> Include metadata `{"type": "user_preference"}`
- **Environment/setup discoveries** -> Include metadata `{"type": "environmental"}`
- **Conventions established** -> Include metadata `{"type": "convention"}`

Memories can be as detailed as needed -- include full context, reasoning, code snippets, file paths, and examples. Longer, searchable memories are more valuable than vague one-liners.

## Before losing context

If context is about to be compacted or the session is ending, store a comprehensive session summary:

```
## Session Summary

### User's Goal
[What the user originally asked for]

### What Was Accomplished
[Numbered list of tasks completed]

### Key Decisions Made
[Architectural choices, trade-offs discussed]

### Files Created or Modified
[Important file paths with what changed]

### Current State
[What is in progress, pending items, next steps]
```

Include metadata: `{"type": "session_state"}`

## Memory hygiene

- Do NOT write to MEMORY.md or any file-based memory. Use mem0 MCP tools exclusively.
- Only store genuinely useful learnings. Skip trivial interactions.
- Use specific, searchable language in memory content.
