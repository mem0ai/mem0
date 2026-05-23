---
name: mem0
description: Mem0 SDK reference — Python, TypeScript, and integrations
license: Apache-2.0
metadata:
  author: mem0ai
  version: "0.1.1"
  category: ai-memory
  tags: "memory, personalization, ai, python, typescript, vector-search"
compatibility: Requires Python 3.10+ or Node.js 18+, pip install mem0ai or npm install mem0ai, MEM0_API_KEY env var (Platform), and internet access to api.mem0.ai. Uses Mem0 v3 API.
---

# Mem0 Platform Integration

> **Skill Graph:** This skill is part of the Mem0 skill graph:
> - **mem0** (this skill) -- Platform Client SDK + OSS (Python + TypeScript)
> - **[mem0-vercel-ai-sdk](https://github.com/mem0ai/mem0/tree/main/skills/mem0-vercel-ai-sdk)** -- Vercel AI SDK provider

Mem0 is a managed memory layer for AI applications. It stores, retrieves, and manages user memories via API — no infrastructure to deploy. For self-hosted usage, see the OSS section in the client references below.

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

Get an API key at: https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=mem0-plugin-skill

> **Don't have a `MEM0_API_KEY`?** Sign up at https://app.mem0.ai and create one from the dashboard. Keys start with `m0-`.

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
results = client.search("dietary preferences", filters={"user_id": "alice"})
for mem in results.get("results", []):
    print(mem["memory"])
```

### Get all memories
```python
all_memories = client.get_all(filters={"user_id": "alice"})
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
    memories = mem0.search(user_input, filters={"user_id": user_id})
    context = "\n".join([m["memory"] for m in memories.get("results", [])])

    # 2. Generate response with memory context
    response = openai.chat.completions.create(
        model="gpt-5-mini",
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

## Common edge cases

- **Search returns empty:** v3 processes `add()` asynchronously — returns an event ID immediately. Wait 2-3s before searching. Also verify `user_id` matches exactly (case-sensitive) and use `filters={"user_id": "..."}` syntax.
- **AND filter with user_id + agent_id returns empty:** Entities are stored separately. `{"AND": [{"user_id": "alice"}, {"agent_id": "bot"}]}` returns nothing. Use `OR` instead, or query each separately.
- **Duplicate memories:** Don't mix `infer=True` (default) and `infer=False` for the same data. `infer=True` extracts facts via LLM with dedup. `infer=False` stores raw — same text can be stored twice.
- **Implicit null scoping:** `filters={"user_id": "alice"}` only returns memories where `agent_id`, `app_id`, `run_id` are ALL null. Wrap in `{"OR": [...]}` to include memories with non-null scoping fields.
- **Platform vs OSS imports:** Platform: `from mem0 import MemoryClient`. OSS: `from mem0 import Memory`. Don't mix them — `MemoryClient` talks to `api.mem0.ai`, `Memory` runs locally.
- **v3 defaults:** `top_k=20`, `threshold=0.1`, `rerank=False`. Adjust as needed.

## v3 API (Current)

Mem0 v3 uses single-pass extraction, entity linking, and multi-signal retrieval.

**Key v3 changes from v2:**
- **Endpoints:** `POST /v3/memories/add/`, `POST /v3/memories/search/`, `POST /v3/memories/` (paginated list)
- **Extraction:** Single ADD-only pass — no more UPDATE/DELETE operations during extraction. Memories accumulate rather than consolidate.
- **Entity linking:** Replaces graph memory. Auto-extracted during `add()`, no config needed. Remove `enable_graph` and `graph_store` from any old config.
- **Defaults:** `top_k=20`, `threshold=0.1`, `rerank=False`
- **Removed params:** `org_id`, `project_id`, `enable_graph` — all removed from SDK
- **TypeScript:** Exclusively camelCase (`userId`, `agentId`, `appId`, `topK`)
- **Add response:** Async — returns event ID immediately, poll via `GET /v1/event/{event_id}/`

See the [migration guide](https://docs.mem0.ai/migration/platform-v2-to-v3) for details.

## Live documentation search

For the latest docs beyond what's in the references, use the doc search tool:

```bash
python ${CLAUDE_SKILL_DIR}/scripts/mem0_doc_search.py --query "topic"
python ${CLAUDE_SKILL_DIR}/scripts/mem0_doc_search.py --page "/platform/features/graph-memory"
python ${CLAUDE_SKILL_DIR}/scripts/mem0_doc_search.py --index
```

No API key needed — searches docs.mem0.ai directly.

## Client SDK References

Language-specific deep references (Platform + OSS):

| Language | File |
|----------|------|
| Python (MemoryClient + AsyncMemoryClient + Memory OSS) | [client/python.md](client/python.md) |
| TypeScript/Node.js (MemoryClient + Memory OSS) | [client/node.md](client/node.md) |
| Python vs TypeScript differences | [client/differences.md](client/differences.md) |

## Platform References

Load these on demand for deeper detail:

| Topic | File |
|-------|------|
| Quickstart (Python, TS, cURL) | [references/quickstart.md](references/quickstart.md) |
| SDK guide (all methods, both languages) | [references/sdk-guide.md](references/sdk-guide.md) |
| API reference (endpoints, filters, object schema) | [references/api-reference.md](references/api-reference.md) |
| Architecture (pipeline, lifecycle, scoping, performance) | [references/architecture.md](references/architecture.md) |
| Platform features (retrieval, graph, categories, MCP, etc.) | [references/features.md](references/features.md) |
| Framework integrations (LangChain, CrewAI, OpenAI Agents, etc.) | [references/integration-patterns.md](references/integration-patterns.md) |
| Use cases & examples (real-world patterns with code) | [references/use-cases.md](references/use-cases.md) |

## Related Mem0 Skills

| Skill | When to use | Link |
|-------|-------------|------|
| mem0-vercel-ai-sdk | Vercel AI SDK provider with automatic memory | [GitHub](https://github.com/mem0ai/mem0/tree/main/skills/mem0-vercel-ai-sdk) |
