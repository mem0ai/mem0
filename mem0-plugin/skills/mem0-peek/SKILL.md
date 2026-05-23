---
name: mem0-peek
description: Quick search memories — compact one-liner results
---

# Mem0 Peek

Quick search with compact output. Lighter than `/mem0:tour`.

## Execution

### Step 1: Parse query

The user provides a search query: `/mem0:peek auth middleware`

If no query provided, ask: "What should I search for?"

### Step 2: Search

Run 2 parallel `search_memories` calls:

1. Broad: `query=<user's query>`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}`, `top_k=10`
2. Targeted: `query=<user's query>`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}, {"metadata": {"type": "decision"}}]}`, `top_k=5`

### Step 3: Display

Deduplicate by ID, then show compact results:

```
## mem0 peek: "<query>" (<N> results)

1. [decision] Auth module uses JWT with RS256 keys (2025-05-15) [mem0:a3f8b2c1]
2. [anti_pattern] Don't use symmetric HS256 — leaked in env (2025-05-10) [mem0:7e2d9f4a]
3. [convention] All middleware in src/middleware/ (2025-05-08) [mem0:c4d5e6f7]
```

Format: `<number>. [<type>] <content, 80 chars> (<date>) [mem0:<short_id>]`

If no results:
```
No memories matching "<query>" for project <project_id>.
```
