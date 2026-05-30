---
name: "mem0:remember"
description: Stores a memory verbatim from user input with appropriate type classification and metadata. Use when the user says remember this, save this, store this, note that, or explicitly asks to record a decision, preference, convention, or learning.
---

# Mem0 Remember

Store a fact or learning directly into mem0.

## Execution

### Step 1: Extract the content

The user provides the content as an argument: `/mem0:remember <text>`

If no text was provided, ask: "What should I remember?"

### Step 2: Classify the memory

Based on the content, pick the best `metadata.type`:

| Content signal | Type |
|---|---|
| "we decided...", "always use...", "never..." | `decision` |
| "X doesn't work because...", "don't try..." | `anti_pattern` |
| "I prefer...", "use X instead of Y" | `user_preference` |
| "the convention is...", "we always..." | `convention` |
| "learned that...", "figured out..." | `task_learning` |
| setup, env, tooling, config | `environmental` |
| anything else | `task_learning` |

### Step 3: Store

Call `add_memory` with:
- `text="<the user's text>"`
- `user_id=<active_user_id>`
- `app_id=<active_project_id>`
- `metadata={"type": "<classified_type>", "branch": "<active_branch>", "confidence": 1.0, "source": "remember_command"}`
- `infer=False`

`infer=False` because the user stated the fact explicitly — no extraction needed.
`confidence=1.0` because the user explicitly asked to store this.

### Step 4: Confirm

The `add_memory` response returns `event_id` (not `memory_id`) because writes are async.
Call `get_event_status(event_id=<event_id>)` once.

- If status is `SUCCEEDED`: print the memory ID from the result.
- If status is `PENDING` or `processing`: print with the event ID as fallback.

```
Remembered as <type>: "<content, first 80 chars>"
Memory ID: <id from event status>
```

Append `...` only if content was truncated (longer than 80 chars).

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
