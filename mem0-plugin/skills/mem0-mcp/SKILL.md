---
name: mem0-mcp
description: >
  Mem0 memory protocol for agents using the mem0 MCP tools (Claude Code, Cursor,
  Codex, and any other MCP-aware runtime). Decide deliberately when memory context
  would help, run targeted searches with metadata filters when it would, and store
  key learnings as work completes. Use the mem0 MCP tools (add_memory,
  search_memories, get_memories, etc.) for all memory operations.
---

# Mem0 MCP Memory Protocol

You have access to persistent memory via the mem0 MCP tools. Follow this protocol to maintain context across sessions.

## On every new task

Decide whether persistent memory context would improve your response, then act accordingly. Don't search by default — search deliberately.

### Decide: search or skip?

**Search WHEN** the user:
- references past work, decisions, or things "we" built
- asks "how should we...", "best way to...", or any decision-style question
- hits an error, bug, or asks for debugging help
- requests work that touches their stack, tools, conventions, or preferences
- starts a non-trivial task in a known project

**Skip WHEN:**
- the prompt is an acknowledgement or continuation ("ok", "thanks", "continue")
- the user is *stating* new info — that's a write trigger (`add_memory`), not a search
- it's a pure syntax / factual question answerable from general knowledge
- you already searched this scope earlier in the turn

Empty results are normal. Proceed without context — they don't mean the system is broken.

### How to search well

When you do search, run **2–4 parallel** `search_memories` calls at different angles instead of one query echoing the user's prompt.

**Query phrasing:**
- Use **nouns**, not sentences. `"auth module decisions"` beats `"what did we decide about auth"`.
- Strip conversational filler. *"remember when we picked Postgres?"* → search `"Postgres choice"`.
- Use entity names, not pronouns. Resolve "that thing" from recent context first.
- Don't search on meta-questions ("what was that?") — use recent context or `get_memories` ordered by `created_at`.

**Metadata filters** match the same `type` values written under "After completing significant work" below.

Two rules from the v2 filter spec:

1. The root **must** be a logical operator (`AND` / `OR` / `NOT`) with an array. A bare `{"user_id": "..."}` won't work.
2. Metadata uses a **nested** object, not a dotted key. `{"metadata": {"type": "decision"}}`, never `{"metadata.type": "decision"}`. Only top-level metadata keys are filterable.

Combine `user_id` with one metadata clause per call:

| `metadata.type` clause | Use for |
|--------|---------|
| `{"metadata": {"type": "decision"}}` | design / architecture / "how should we" questions |
| `{"metadata": {"type": "anti_pattern"}}` | debugging, error handling, things that failed before |
| `{"metadata": {"type": "user_preference"}}` | tooling, stack, style — always include for code work |
| `{"metadata": {"type": "convention"}}` | established patterns in this project |

Full filter (replace `<your_user_id>` with the active user_id from your runtime):
```python
filters={"AND": [{"user_id": "<your_user_id>"}, {"metadata": {"type": "decision"}}]}
```

### Worked example

User asks: *"Refactor the auth module to use JWT."*

Don't:
```python
search_memories(query="Refactor the auth module to use JWT")
# Hits whatever shares words. Misses prior decisions and preferences.
```

Do (parallel — substitute the active `user_id` for `<your_user_id>`):
```python
search_memories(query="auth module decisions",
                filters={"AND": [{"user_id": "<your_user_id>"}, {"metadata": {"type": "decision"}}]})
search_memories(query="JWT",
                filters={"AND": [{"user_id": "<your_user_id>"}]})
search_memories(query="auth refactor failures",
                filters={"AND": [{"user_id": "<your_user_id>"}, {"metadata": {"type": "anti_pattern"}}]})
search_memories(query="auth",
                filters={"AND": [{"user_id": "<your_user_id>"}, {"metadata": {"type": "user_preference"}}]})
```

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
