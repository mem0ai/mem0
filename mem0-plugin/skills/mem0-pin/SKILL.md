---
name: mem0-pin
description: >
  Pin important memories so they surface prominently and are protected from
  consolidation. New pins use immutable: true (SDK v2.1.33+) to prevent
  deduplication from modifying or removing the memory. Existing memories get
  metadata.pinned: true as a search-time filter; full consolidation protection
  requires delete + re-add. TRIGGER: user runs /mem0:pin <query or ID>, or
  says "pin this memory", "mark as important", "always remember this".
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

There are two sub-cases depending on whether the user wants to pin an **existing** memory or create a **new** pinned memory from scratch.

#### 3a: Pinning a new memory (preferred path for full protection)

Use `add_memory` with `immutable: true` as a top-level parameter. The `immutable` flag is a first-class platform parameter (added in SDK v2.1.33) that prevents the memory from being modified or removed by consolidation/deduplication. `metadata.pinned: true` is also included as a search-time filter aid.

```python
add_memory(
    messages=[{"role": "user", "content": "<text to pin>"}],
    user_id=<user_id>,
    immutable=True,
    metadata={"pinned": True},
)
```

#### 3b: Pinning an existing memory

Call `update_memory` with:
- `memory_id=<selected_id>`
- `data=<original_text>` (preserve the existing content)
- `metadata=` merge `original_metadata` with `{"pinned": true}`

```python
updated_meta = {**original_metadata, "pinned": True}
update_memory(memory_id=<selected_id>, data=<original_text>, metadata=updated_meta)
```

**Important:** `update_memory` requires the `data` (text) parameter. Passing only metadata may error or wipe content. Always read first, then update with the full text and explicit metadata.

**Consolidation-protection limitation:** `update_memory` cannot set the `immutable` flag on an existing memory. If the user needs full consolidation protection for an existing memory, they must delete it and re-add it using `add_memory` with `immutable: true` (path 3a above). In the confirm step (Step 4), note this limitation if the user pinned an existing memory via `update_memory`.

### Step 4: Confirm

For new pins created via `add_memory` with `immutable: true`:
```
Pinned: "<memory content, first 80 chars>..."
Memory ID: <id>
Pinned with consolidation protection (immutable). This memory will not be modified or removed by deduplication.
```

For existing memories pinned via `update_memory`:
```
Pinned: "<memory content, first 80 chars>..."
Memory ID: <id>
Pinned memories surface first when relevant to a search.
Note: consolidation protection (immutable flag) requires delete + re-add. Say "re-pin this with full protection" to do that.
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
