---
name: remember
description: Save a memory verbatim from your input
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
- `messages=[{"role": "user", "content": "<the user's text>"}]`
- `user_id=<active_user_id>`
- `app_id=<active_project_id>`
- `metadata={"type": "<classified_type>", "branch": "<active_branch>", "confidence": 1.0, "source": "remember_command"}`
- `infer=False`

`infer=False` because the user stated the fact explicitly — no extraction needed.
`confidence=1.0` because the user explicitly asked to store this.

### Step 4: Confirm

Print:
```
Remembered as <type>: "<content, first 80 chars>"
Memory ID: <id>
```

Append `...` only if content was truncated (longer than 80 chars).
