---
name: memory-dream
description: >
  Memory consolidation protocol. Reviews all stored memories, merges duplicates,
  removes noise and credentials, rewrites unclear entries, and enforces TTL expiration.
  Use when the user asks to clean up, consolidate, or review their memories.
  Also triggers automatically after sufficient activity (configurable).
user-invocable: true
metadata:
  {"openclaw": {"injected": true, "emoji": "💤", "requires": {"env": ["MEM0_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"], "bins": []}}}
---

# Memory Consolidation

You are performing a memory consolidation pass. Your goal is to review all stored memories for this user and improve their overall quality. Think of this as compressing raw observations into clean, durable knowledge.

## Available Tools

### memory_search
Semantic search across stored memories.
- `query` (required): search query
- `limit`: max results
- `userId`, `agentId`: scope overrides
- `scope`: `"all"` (default), `"session"`, or `"long-term"`
- `categories`: filter by category array

### memory_add
Store new facts in long-term memory.
- `facts` (required): array of facts — ALL must share the same category
- `category`: `"identity"`, `"preference"`, `"decision"`, `"rule"`, `"project"`, `"configuration"`, `"technical"`, `"relationship"`
- `importance`: 0.0–1.0

### memory_get
Retrieve a single memory by ID.
- `memoryId` (required): the memory ID

### memory_list
List all stored memories for a user or agent.
- `userId`, `agentId`: scope overrides
- `scope`: `"all"` (default), `"session"`, or `"long-term"`

### memory_update
Update an existing memory's text in place. Atomic and preserves edit history.
- `memoryId` (required): the memory ID to update
- `text` (required): the new text (replaces old)

### memory_delete
Delete memories by ID, query, or bulk.
- `memoryId`: specific memory ID to delete
- `all`: delete ALL memories (requires `confirm: true`)
- `userId`, `agentId`: scope overrides

### memory_event_list
List recent background processing events (platform mode only).

### memory_event_status
Get status of a specific background event.
- `event_id` (required): the event ID to check

Follow these four phases in order. Do not skip phases.

## Phase 1: Orient

Survey the current memory landscape before making any changes.

1. Call `memory_list` to load all stored memories.
2. Count memories by category. Note the total.
3. Identify the oldest and newest memories by their timestamps.
4. Note any obvious problems visible in the list: duplicates, very short entries, entries without temporal anchors.

Do not modify anything in this phase. The goal is to understand what you are working with.

## Phase 2: Gather Targets

Identify which memories need action. Use the tools to investigate.

**Search for recent additions:**
Call `memory_search` with a `created_at` filter to find memories added since the last consolidation. These are the most likely to need merging or cleanup.

**Classify each target into one of these actions:**
- DELETE: contains credentials, expired by TTL, pure noise, raw tool output, standalone timestamps
- MERGE: two or more memories express the same fact in different words, or a series tracks incremental changes to the same entity
- REWRITE: vague, missing temporal anchor, uses first person instead of third, wrong category, overly verbose

## Phase 3: Consolidate

Execute the actions identified in Phase 2. Work in this priority order:

### 3a. Delete dangerous and expired entries

Delete immediately using `memory_delete`:
- Credentials, API keys, tokens, passwords, secrets (matching known credential prefixes and auth patterns injected by the plugin at runtime)
- Pure timestamps with no context
- Raw tool output stored as memory
- Heartbeat or cron execution records
- Generic acknowledgments stored as memory ("ok", "got it")
- Operational memories older than 7 days
- Project memories older than 90 days

### 3b. Merge duplicates

When two or more memories express the same fact:
1. Pick the most complete version as the base
2. Call `memory_update` on the best version to incorporate missing details from the others
3. Call `memory_delete` on the redundant entries

`memory_update` is preferred over forget-then-store because it is atomic and preserves edit history.

When merging, follow these rules:
- Keep the user's original words for opinions and preferences
- Preserve temporal anchors from both versions
- Do not exceed 50 words in the merged result
- The merged memory must be self-contained (understandable without the deleted ones)

### 3c. Rewrite unclear entries

When a memory needs improvement but is not a duplicate:
1. Call `memory_update` with the improved text

Rewrite when:
- Memory uses first person ("I prefer") instead of third ("User prefers")
- Memory lacks a temporal anchor for time-sensitive information
- Memory is vague ("likes python") and can be made specific ("User prefers Python for backend development")
- Memory has the wrong category assignment
- Memory is over 50 words and can be compressed without losing information

## Phase 4: Report

After completing all operations, summarize what you did:

```
Consolidation complete.
- Reviewed: [total count]
- Deleted (credentials/secrets): [count]
- Deleted (expired/stale): [count]
- Merged: [count] groups into [count] memories
- Rewritten: [count]
- Final count: [total remaining]
- Issues found: [any notable problems or observations]
```

## Quality Targets

After consolidation, the memory store should have:
- Zero memories containing credentials or secrets
- Zero duplicate memories (same fact in different words)
- All project and operational memories have temporal anchors ("As of YYYY-MM-DD")
- All memories use third person voice
- All memories are correctly categorized
- Each memory is 15-50 words, self-contained, and atomic (one fact per memory)
