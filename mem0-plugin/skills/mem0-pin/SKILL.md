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

### Step 2: Read current content

Call `get_memory` with the selected memory ID. Store:
- `original_text` — the memory's `content` (text) field
- `original_metadata` — the existing `metadata` dict

This is required because `update_memory` replaces the full memory — a metadata-only call would wipe the text content.

### Step 3: Pin it

Call `update_memory` with:
- `memory_id=<selected_id>`
- `data=<original_text>` (preserve the existing content)
- `metadata=` merge `original_metadata` with `{"pinned": true}`

Example:
```python
updated_meta = {**original_metadata, "pinned": True}
update_memory(memory_id=<selected_id>, data=<original_text>, metadata=updated_meta)
```

**Important:** `update_memory` requires the `data` (text) parameter. Passing only metadata may error or wipe content. Always read first, then update with the full text and explicit metadata.

### Step 4: Confirm

```
Pinned: "<memory content, first 80 chars>..."
Memory ID: <id>
Pinned memories surface first when relevant to a search.
```

### Unpin

If the user says "unpin" or `/mem0:unpin`:
1. Call `get_memory` to read current content and metadata.
2. Set `metadata.pinned = false` explicitly:
   ```python
   updated_meta = {**original_metadata, "pinned": False}
   update_memory(memory_id=<id>, data=<original_text>, metadata=updated_meta)
   ```
3. Print: `Unpinned: "<content>..."`
