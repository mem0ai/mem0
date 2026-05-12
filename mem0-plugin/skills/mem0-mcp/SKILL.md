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

> `metadata.type` (which you set explicitly) and `categories` (which the platform auto-tags after the project's custom-category list — see `scripts/setup_coding_categories.py`) are complementary. Always set `metadata.type` for explicit filtering; the platform fills in `categories` on its own. Don't try to set `categories` on `add_memory` calls — per-request overrides aren't supported on the managed API.

### Expiration: high-churn vs durable

Some memory types are state snapshots that go stale fast; others are durable facts that should outlive the session that created them. Mark the difference with `expiration_date` on writes.

| Type | Expiration | Why |
|---|---|---|
| `session_state`, `compact_summary` | `expiration_date` ≈ today + 90 days | Describe a single moment of project state. Useless after a quarter; clutter the recall surface. |
| `decision`, `anti_pattern`, `convention`, `user_preference`, `task_learning`, `environmental` | omit `expiration_date` | Durable facts. A decision made last year is still a decision; same for a convention or a user preference. |

`add_memory` accepts `expiration_date` as a string (`"YYYY-MM-DD"`). The two server-side hooks (`on_pre_compact.py`, `capture_compact_summary.py`) already set this for the types they write. When you write directly via the MCP tool, follow the same rule.

### Recency filter on recall

When the user is asking about *current* state ("where were we", "what's the active task", "the latest decision on X"), filter recall to recent memories so stale snapshots don't surface:

```python
# Last 90 days only
{"AND": [{"user_id": "<id>"}, {"metadata": {"type": "session_state"}}, {"created_at": {"gte": "<90 days ago, YYYY-MM-DD>"}}]}
```

Skip the recency filter when the user is asking about durable facts ("what conventions does this project use", "have we hit this bug before") — those are timeless and recency would hide them.

Memories can be as detailed as needed -- include full context, reasoning, code snippets, file paths, and examples. Longer, searchable memories are more valuable than vague one-liners.

### Use `infer=False` for already-structured content

When you've done the extraction work yourself — pre-compaction summaries, decisions, anti-patterns, conventions you've explicitly identified — pass `infer=False` so the platform stores your text verbatim instead of running a second extraction pass over it.

```python
add_memory(
    messages=[{"role": "user", "content": "<your structured fact>"}],
    user_id="<active user_id>",
    metadata={"type": "decision"},
    infer=False,
)
```

Stick to one mode per distinct piece of content — don't mix `infer=True` (default) and `infer=False` for the same fact, you'll get duplicates. Default (`infer=True`) is right for raw conversational signal you want extracted; `infer=False` is right for pre-extracted structure.

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
