---
name: pin
description: Pins or unpins a memory to protect it from pruning during dream consolidation. Use when a memory is critical and must never be removed, such as architecture decisions, security constraints, or immutable team conventions.
---

# Mem0 Pin

Pin a memory to mark it as high-priority and protect from pruning.

## Execution

### Step 1: Find the memory

The user provides either a search query or memory ID.

**If memory ID:**
- Call `get_memory` with the ID.

**If search query:**
- Call `search_memories` with the query, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}`, `top_k=5`.
- Show numbered list with content previews.
- Ask: "Which memory to pin? Enter a number."

### Step 2: Read current content

Call `get_memory` with the selected memory ID. Store:
- `original_text` — the memory's text content
- `original_metadata` — the existing `metadata` dict

### Step 3: Pin it

Call `update_memory` with:
- `memory_id=<selected_id>`
- `text=<original_text>` (preserve existing content)
- `metadata=` merge `original_metadata` with `{"pinned": true}`

```python
updated_meta = {**original_metadata, "pinned": True}
update_memory(memory_id=<selected_id>, text=<original_text>, metadata=updated_meta)
```

**Important:** `update_memory` requires the `text` parameter. Passing only metadata may error or wipe content.

**For new memories** (user wants to pin text that isn't stored yet):
1. Call `add_memory` with the text + `metadata={"pinned": true, "type": "decision", "confidence": 1.0}`
2. Confirm with the memory ID from the result

### Step 4: Confirm

```
Pinned: "<memory content, first 80 chars>"
Memory ID: <id>
```

Append `...` only if content exceeds 80 characters.

### Unpin

If the user says "unpin":
1. Call `get_memory` to read current content and metadata.
2. Set `metadata.pinned = false`:
   ```python
   updated_meta = {**original_metadata, "pinned": False}
   update_memory(memory_id=<id>, text=<original_text>, metadata=updated_meta)
   ```
3. Print: `Unpinned: "<content>..."`
