---
name: pin
description: Pins or unpins a memory to protect it from pruning during dream consolidation. Use when a memory is critical and must never be removed, such as core preferences, important decisions, or immutable personal facts.
---

# Pin

Pin a memory to mark it as high-priority and protect from dream pruning.

## Execution

### Step 1: Find the memory

The user provides either a search query or memory ID.

**If memory ID:** Look it up directly.

**If search query:**
- Use `mem0_memory` tool with `action="search"`, `query=<query>`.
- Show numbered list with content previews.
- Ask: "Which memory to pin? Enter a number."

### Step 2: Pin it

Pinning works by prepending `[PINNED]` to the memory text. This marker tells the dream consolidation to skip it during pruning.

Use `mem0_memory` tool with `action="add"`, `content="[PINNED] <original memory text>"`.

Then delete the original using `mem0_memory` with `action="delete"` and the original memory ID.

**For new memories** (user wants to pin text that isn't stored yet):
- Use `mem0_memory` tool with `action="add"`, `content="[PINNED] <the user's text>"`.

### Step 3: Confirm

```
Pinned: "<memory content, first 80 chars>"
```

Append `...` only if content exceeds 80 characters.

### Unpin

If the user says "unpin":
1. Find the memory (search or by ID).
2. Create a new memory without the `[PINNED]` prefix.
3. Delete the pinned version.
4. Print: `Unpinned: "<content>..."`
