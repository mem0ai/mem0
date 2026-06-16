---
name: "mem0:pin"
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

The `update_memory` tool updates a memory by `id`. To pin durably, append a pin
marker to the text so it travels with the memory:

```python
pinned_text = "[PINNED] " + original_text if not original_text.startswith("[PINNED]") else original_text
update_memory(id=<selected_id>, text=pinned_text)
```

**For new memories** (user wants to pin text that isn't stored yet):
1. Call `add_memory` with:
   - `text="[PINNED] <the user's text>"`
   - `user_id=<active_user_id>`
   - `app_id=<active_project_id>`
   - `metadata={"pinned": true, "type": "decision", "confidence": 1.0}`
   - `infer=False`
2. The response contains `event_id`. Call `get_event_status(event_id=<event_id>)` once to retrieve the memory ID, then confirm.

### Step 4: Confirm

```
Pinned: "<memory content, first 80 chars>"
Memory ID: <id>
```

Append `...` only if content exceeds 80 characters.

### Unpin

If the user says "unpin":
1. Call `get_memory` to read current content.
2. Remove the pin marker from the text:
   ```python
   unpinned_text = original_text.removeprefix("[PINNED] ")
   update_memory(memory_id=<id>, text=unpinned_text)
   ```
3. Print: `Unpinned: "<content>..."`

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
