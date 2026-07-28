---
name: health
description: Diagnose mem0 connectivity, credentials, project configuration and read/write health. Use when memory operations fail, searches return nothing, the context pack is empty, or to verify the plugin is working.
---

# Health check

```bash
mem0-agent health          # connectivity, identity, scope, config, breaker
mem0-agent health --deep   # adds a real write probe and a corpus quality scan
```

Read the output top-down and stop at the first failure — later checks depend on earlier ones.

## What each failure means

| Symptom | Cause | Fix |
|---|---|---|
| `no API key` | not in env or keychain | `mem0-agent onboard`, or export `MEM0_API_KEY` |
| `identity unavailable` | key rejected or network down | verify the key at app.mem0.ai |
| `circuit open` | 3 consecutive API failures | wait out the cooldown; memory is paused, sessions are unaffected |
| `config incomplete` | instructions/categories/decay not applied | `mem0-agent setup` |
| pack empty, corpus non-empty | scope mismatch | compare `user_id`/`app_id` against `mem0-agent stats` |
| a just-written memory is missing | extraction is asynchronous (20s–5min) | wait, then re-check — this is normal, not a fault |

## Things that look broken but aren't

- **Categories are empty on new memories.** Categorization is a background job running
  hours behind writes. Retrieval filters on `metadata.type`, which is set at write time, so
  this does not affect recall.
- **A memory you deleted still exists in the database.** Deletes are soft; the record is
  hidden from every read path.
- **Nothing was captured this session.** Most turns should capture nothing. Check
  `mem0-agent stats` for the drop/flag breakdown before assuming a bug.

Report findings plainly. If everything passes, say so in one line and include the corpus
size and current scope.
