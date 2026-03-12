---
name: mem0
description: >
  Integrate Mem0 Platform into AI applications for persistent memory, personalization, and semantic search.
  Use this skill when the user mentions "mem0", "memory layer", "remember user preferences",
  "persistent context", "personalization", or needs to add long-term memory to chatbots, agents,
  or AI apps. Covers Python and TypeScript SDKs, framework integrations (LangChain, CrewAI,
  Vercel AI SDK, OpenAI Agents SDK, Pipecat), and the full Platform API. Use even when the user
  doesn't explicitly say "mem0" but describes needing conversation memory, user context retention,
  or knowledge retrieval across sessions.
license: Apache-2.0
metadata:
  author: mem0ai
  version: "1.0.0"
  category: ai-memory
  tags: "memory, personalization, ai, python, typescript, vector-search"
compatibility: Requires Python 3.10+ or Node.js 18+, pip install mem0ai or npm install mem0ai, MEM0_API_KEY env var, and internet access to api.mem0.ai
---

# Mem0 Platform Integration

Mem0 is a managed memory layer for AI applications. It stores, retrieves, and manages user memories via API — no infrastructure to deploy.

## Step 1: Install and authenticate

**Python:**
```bash
pip install mem0ai
export MEM0_API_KEY="m0-your-api-key"
```

**TypeScript/JavaScript:**
```bash
npm install mem0ai
export MEM0_API_KEY="m0-your-api-key"
```

Get an API key at: https://app.mem0.ai/dashboard/api-keys

## Step 2: Initialize the client

**Python:**
```python
from mem0 import MemoryClient
client = MemoryClient(api_key="m0-xxx")
```

**TypeScript:**
```typescript
import MemoryClient from 'mem0ai';
const client = new MemoryClient({ apiKey: 'm0-xxx' });
```

For async Python, use `AsyncMemoryClient`.

## Step 3: Core operations

Every Mem0 integration follows the same pattern: **retrieve → generate → store**.

### Add memories
```python
messages = [
    {"role": "user", "content": "I'm a vegetarian and allergic to nuts."},
    {"role": "assistant", "content": "Got it! I'll remember that."}
]
client.add(messages, user_id="alice")
```

### Search memories
```python
results = client.search("dietary preferences", user_id="alice")
for mem in results.get("results", []):
    print(mem["memory"])
```

### Get all memories
```python
all_memories = client.get_all(user_id="alice")
```

### Update a memory
```python
client.update("memory-uuid", text="Updated: vegetarian, nut allergy, prefers organic")
```

### Delete a memory
```python
client.delete("memory-uuid")
client.delete_all(user_id="alice")  # delete all for a user
```

## Common integration pattern

```python
from mem0 import MemoryClient
from openai import OpenAI

mem0 = MemoryClient()
openai = OpenAI()

def chat(user_input: str, user_id: str) -> str:
    # 1. Retrieve relevant memories
    memories = mem0.search(user_input, user_id=user_id)
    context = "\n".join([m["memory"] for m in memories.get("results", [])])

    # 2. Generate response with memory context
    response = openai.chat.completions.create(
        model="gpt-4.1-nano-2025-04-14",
        messages=[
            {"role": "system", "content": f"User context:\n{context}"},
            {"role": "user", "content": user_input},
        ]
    )
    reply = response.choices[0].message.content

    # 3. Store interaction for future context
    mem0.add(
        [{"role": "user", "content": user_input}, {"role": "assistant", "content": reply}],
        user_id=user_id
    )
    return reply
```

## API endpoints

| Operation | Method | Endpoint |
|-----------|--------|----------|
| Add | POST | `/v1/memories/` |
| Search | POST | `/v2/memories/search/` |
| Get All | POST | `/v2/memories/` |
| Get One | GET | `/v1/memories/{id}/` |
| Update | PUT | `/v1/memories/{id}/` |
| Delete | DELETE | `/v1/memories/{id}/` |

Base URL: `https://api.mem0.ai` — Auth header: `Authorization: Token <MEM0_API_KEY>`

## Common edge cases

- **Search returns empty:** Memories process asynchronously. Wait 2-3s after `add()` before searching. Also verify `user_id` matches exactly (case-sensitive).
- **AND filter with user_id + agent_id returns empty:** Entities are stored separately. Use `OR` instead, or query separately.
- **Duplicate memories:** Don't mix `infer=True` (default) and `infer=False` for the same data. Stick to one mode.
- **Wrong import:** Always use `from mem0 import MemoryClient` (or `AsyncMemoryClient` for async). Do not use `from mem0 import Memory`.

## Available scripts

Run these directly for memory operations:

- **`scripts/add_memory.py`** — Add memories from CLI. Usage: `python scripts/add_memory.py --user_id USER --message "text"`
- **`scripts/search_memory.py`** — Search with filters. Usage: `python scripts/search_memory.py --user_id USER --query "text"`
- **`scripts/update_memory.py`** — Update by ID. Usage: `python scripts/update_memory.py --memory_id ID --text "new text"`
- **`scripts/delete_memory.py`** — Delete by ID or bulk. Usage: `python scripts/delete_memory.py --memory_id ID`
- **`scripts/get_memories.py`** — List memories. Usage: `python scripts/get_memories.py --user_id USER`
- **`scripts/mem0_doc_search.py`** — Search latest Mem0 docs. Usage: `python scripts/mem0_doc_search.py --query "topic"`

All scripts require `MEM0_API_KEY` env var. Run with `--help` for full options.

## References

Load these on demand for deeper detail:

| Topic | File |
|-------|------|
| Full quickstart (Python, TS, cURL) | [references/quickstart.md](references/quickstart.md) |
| API concepts, endpoints, memory object shape | [references/general.md](references/general.md) |
| Add memory (all options, graph, multimodal) | [references/add-memory.md](references/add-memory.md) |
| Search memory (filters, operators, gotchas) | [references/search-memory.md](references/search-memory.md) |
| Update and delete operations | [references/update-delete.md](references/update-delete.md) |
| V2 filter system (AND/OR/NOT, operators) | [references/filters.md](references/filters.md) |
| Graph memory (entity relations) | [references/graph-memory.md](references/graph-memory.md) |
| Platform features (categories, webhooks, multimodal) | [references/features.md](references/features.md) |
| TypeScript/JavaScript SDK (full API reference) | [references/typescript-sdk.md](references/typescript-sdk.md) |
| Framework integrations (LangChain, CrewAI, Vercel AI, etc.) | [references/integration-patterns.md](references/integration-patterns.md) |
| Use cases & examples (8 real-world patterns with code) | [references/use-cases.md](references/use-cases.md) |
