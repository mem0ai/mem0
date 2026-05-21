---
name: mem0-pin
description: >
  Pin important memories so they surface prominently. Updates metadata to mark
  a memory as pinned. Pinned memories should be prioritized during search.
  TRIGGER: user runs /mem0:pin <query or ID>, or says "pin this memory",
  "mark as important", "always remember this".
---

# Mem0 Pin

Pin a memory to mark it as high-priority.

## Execution

### Step 1: Find the memory

The user provides either a search query or memory ID.

**If memory ID:**
- Call `get_memory` with the ID.

**If search query:**
- Call `search_memories` with the query, `user_id`, `app_id`, `limit=5`.
- Show numbered list with content previews.
- Ask: "Which memory to pin? Enter a number."

### Step 2: Pin it

Call `update_memory` with:
- `memory_id=<selected_id>`
- `metadata={"pinned": true}`

The `pinned: true` metadata flag signals importance. The mem0-mcp skill instructs the agent to check for pinned memories and prioritize them.

### Step 3: Confirm

```
Pinned: "<memory content, first 80 chars>..."
Memory ID: <id>
Pinned memories surface first when relevant to a search.
```

### Unpin

If the user says "unpin" or the memory is already pinned:
- Call `update_memory` with `metadata={"pinned": false}`
- Print: `Unpinned: "<content>..."`
