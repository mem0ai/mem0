---
name: stats
description: Show what memory captured and retrieved, by type and over time, including what was dropped and why. Use when the user asks how many memories exist, what got stored this session, or whether memory is actually helping.
---

# Stats

```bash
mem0-agent stats             # this session plus the corpus for this project
mem0-agent stats --session   # just this session's capture/injection activity
```

## What to look at

**Session view** — how many turns were seen, hard-dropped, flagged, and written, plus which
memories were served in the context pack and whether any were referenced. Dropped counts
are grouped by reason, so "why didn't it save that?" has an actual answer.

**Corpus view** — memories by type and age for the current `user_id` + `app_id`.

## Reading the numbers

- **A high drop rate is correct.** Most turns contain nothing durable. The previous version
  wrote ~98 memories a day and the corpus became unusable; this one targets fewer than 15.
- **Writes ≫ reads is the warning sign**, not a large drop count. If the corpus grows every
  day but the pack is never referenced, the value isn't there — lower `capture` or
  investigate what's being stored.
- **A memory written minutes ago may not appear yet.** Extraction is asynchronous
  (20s–5min). Don't report it as missing.
- **`categories` being empty is expected** on anything less than a few hours old;
  retrieval uses `metadata.type` instead.

Summarize in prose — counts by type, what was captured this session, and whether the served
memories were used. Only surface raw ids when the user is chasing a specific memory.
