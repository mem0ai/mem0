---
name: memory-dream
description: >
  Memory consolidation protocol. Reviews all stored memories, merges duplicates,
  removes noise and credentials, rewrites unclear entries, and enforces TTL expiration.
  Use when the user asks to clean up, consolidate, or review their memories.
  Like sleep consolidation — compress episodic noise into clean semantic knowledge.
user-invocable: true
metadata:
  {"openclaw": {"emoji": "💤"}}
---

# Memory Consolidation Protocol

You are running a memory consolidation session. Your goal is to review all stored memories for this user and improve their quality — merge duplicates, delete noise, rewrite unclear entries, and enforce expiration policies.

This is like sleep consolidation in the human brain: compress episodic noise into clean semantic knowledge.

## Process

1. **Load all memories** using `memory_list`
2. **Group by category** — review each category separately
3. **Apply operations** in this priority order:
   a. DELETE dangerous entries (credentials, secrets)
   b. DELETE expired operational memories (older than TTL)
   c. MERGE duplicate/near-duplicate entries
   d. REWRITE unclear or poorly-formatted entries
   e. VERIFY category assignments are correct

## Operations

### DELETE — Remove bad or stale memories

**Delete immediately if:**
- Contains credentials, API keys, tokens, passwords, secrets
  Patterns: sk-, m0-, ghp_, AKIA, Bearer, password=, token=, secret=
- Pure timestamps with no context ("Current time is 3:42 PM")
- Raw tool output stored as memory (bash output, file contents, API responses)
- Heartbeat/cron execution records ("Healthcheck returned OK at 14:32")
- Generic acknowledgments stored as memory ("ok", "got it", "sure")
- Operational memories older than their TTL (default: 7 days for operational, 90 days for project)

**Use `memory_forget` with the memory ID.**

### MERGE — Combine duplicate or overlapping memories

**Merge when:**
- Two or more memories express the same fact in different words
- A series of memories track incremental changes to the same thing
- Multiple operational memories describe the same recurring pattern

**Merge process:**
1. Pick the best version (most complete, most recent timestamp)
2. Call `memory_store` with the merged, clean version
3. Call `memory_forget` on all the old duplicates

**Examples:**
```
BEFORE (3 memories):
  - "User runs healthcheck every 10 minutes"
  - "User has a cron for healthcheck at */10 interval"
  - "User's heartbeat runs every 10 min on Mac mini"
AFTER (1 memory):
  - "User runs a healthcheck cron every 10 minutes on Mac mini"

BEFORE (2 memories):
  - "User's name is Chris"
  - "User is Chris, a senior platform engineer"
AFTER (1 memory):
  - "User's name is Chris, senior platform engineer"
```

### REWRITE — Improve clarity without changing meaning

**Rewrite when:**
- Memory is vague or ambiguous
- Memory lacks temporal anchoring for time-sensitive facts
- Memory uses first person instead of third person
- Memory is overly verbose and can be compressed
- Memory has wrong category assignment

**Rewrite process:**
1. Call `memory_forget` on the old version
2. Call `memory_store` with the improved version and correct metadata

**Examples:**
```
BEFORE: "likes python"
AFTER: "User prefers Python as primary programming language"

BEFORE: "switched to new database"
AFTER: "As of 2026-03-15, user migrated from MongoDB to PostgreSQL"
```

## Quality Criteria

A good memory is:
- **Atomic**: One fact per memory. No compound sentences with unrelated facts.
- **Self-contained**: Understandable without context from other memories.
- **Third person**: "User prefers..." not "I prefer..."
- **Temporally anchored**: Time-sensitive facts start with "As of YYYY-MM-DD, ..."
- **Actionable**: Contains enough detail to inform future behavior.
- **Categorized correctly**: Category matches the content type.

A bad memory is:
- Vague ("user likes stuff")
- Compound ("User is Chris who works at Acme and likes Python and uses Mac")
- Stale without timestamps ("user is working on a project")
- Redundant with other memories
- Contains secrets or credentials
- Raw tool output or logs

## Consolidation Targets

After consolidation, aim for:
- **Zero** memories containing credentials or secrets
- **Zero** duplicate memories (similarity > 0.85)
- **All** project/operational memories have temporal anchors
- **All** memories use third person voice
- **All** memories are correctly categorized
- **Total memory count** reduced by 30-70% (typical for first consolidation)

## Report

After completing consolidation, summarize what you did:
- Memories reviewed: N
- Deleted (credentials): N
- Deleted (expired/stale): N
- Merged: N groups → N memories
- Rewritten: N
- Final count: N
- Issues found: [any notable problems]
