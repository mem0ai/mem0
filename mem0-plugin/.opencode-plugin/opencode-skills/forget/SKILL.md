---
name: "mem0:forget"
description: Deletes memories by search query or memory ID with confirmation before removal. Use when removing outdated decisions, incorrect memories, sensitive data, or cleaning up after experiments. Also handles undo of recent additions.
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
  - `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<project_id>"}]}`
  - `top_k=10`
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

## Undo recent writes

If the user says "undo last N memories" or "undo last write":

1. Check the `MEM0_SESSION_ID` environment variable (set by the plugin's shell.env hook).
2. If `MEM0_SESSION_ID` is set, call `search_memories` with:
   - `query="recently added"`
   - `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<project_id>"}, {"metadata": {"session_id": "<MEM0_SESSION_ID>"}}]}`
   - `top_k=20`
3. Sort results by creation time descending and show the last N entries (default 1). Ask for confirmation.
4. Delete confirmed entries via `delete_memory`.

If `MEM0_SESSION_ID` is not set or the search returns no results, tell the user: "No recent memory IDs tracked this session. Try `/mem0:tour` to browse recent memories, or `/mem0:forget <search query>` to find specific ones."

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
