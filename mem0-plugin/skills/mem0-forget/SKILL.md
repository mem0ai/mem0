---
name: mem0-forget
description: >
  Delete memories by search query or memory ID. Shows matches for confirmation
  before deleting. Safe — always confirms before destructive action.
  TRIGGER: user runs /mem0:forget <query>, or says "forget this", "delete memory",
  "remove that memory about X".
---

# Mem0 Forget

Delete specific memories from mem0.

## Execution

### Step 1: Parse input

The user provides either:
- A search query: `/mem0:forget auth module decisions`
- A memory ID: `/mem0:forget <memory_id>`

If no argument, ask: "What should I forget? Provide a search query or memory ID."

### Step 2: Find memories

**If memory ID provided** (looks like a UUID or hex string):
- Call `get_memory` with the ID to verify it exists.
- Show: `Found: "<memory content first 120 chars>" (created <date>)`

**If search query provided:**
- Call `search_memories` with:
  - `query=<user's query>`
  - `user_id=<active_user_id>`
  - `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<project_id>"}]}`
  - `limit=10`
- Show numbered list:
  ```
  Found <N> memories matching "<query>":
  1. <content, 120 chars> (type: <type>, created: <date>) [ID: <short_id>]
  2. ...
  ```

### Step 3: Confirm

Ask: "Delete which memories? Enter numbers (e.g., 1,3,5), 'all', or 'cancel'."

For a single memory ID, ask: "Delete this memory? [y/N]"

**Never delete without confirmation.** This is destructive.

### Step 4: Delete

For each confirmed memory, call `delete_memory` with the memory ID.

### Step 5: Report

```
Deleted <N> memories.
```

If any deletions failed, report which ones and why.
