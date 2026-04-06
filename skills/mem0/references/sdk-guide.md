# Mem0 SDK Guide

Complete SDK reference for Python and TypeScript. All methods use `MemoryClient` (Platform API).

> **For language-specific deep references (including OSS):** See [client/python.md](../client/python.md) and [client/node.md](../client/node.md). For Python vs TypeScript differences: [client/differences.md](../client/differences.md).

## Initialization

**Python:**
```python
from mem0 import MemoryClient
client = MemoryClient(api_key="m0-your-api-key")
```

**Python (Async):**
```python
from mem0 import AsyncMemoryClient
client = AsyncMemoryClient(api_key="m0-your-api-key")
```

**TypeScript:**
```typescript
import MemoryClient from 'mem0ai';
const client = new MemoryClient({ apiKey: 'm0-your-api-key' });
```

Constructor accepts `apiKey` (required) and `host` (optional, default: `https://api.mem0.ai`).

---

## add() -- Store Memories

**Python:**
```python
messages = [
    {"role": "user", "content": "I'm a vegetarian and allergic to nuts."},
    {"role": "assistant", "content": "Got it! I'll remember that."}
]
client.add(messages, user_id="alice")

# With metadata
client.add(messages, user_id="alice", metadata={"source": "onboarding"})

# With graph memory
client.add(messages, user_id="alice", enable_graph=True)
```

**TypeScript:**
```typescript
await client.add(messages, { user_id: "alice" });
await client.add(messages, { user_id: "alice", metadata: { source: "onboarding" } });
await client.add(messages, { user_id: "alice", enable_graph: true });
```

### Parameters

| Name | Type | Description |
|------|------|-------------|
| `messages` | array | `[{"role": "user", "content": "..."}]` |
| `user_id` | string | User identifier (recommended) |
| `agent_id` | string | Agent identifier |
| `run_id` | string | Session identifier |
| `metadata` | object | Custom key-value pairs |
| `enable_graph` | boolean | Activate knowledge graph |
| `infer` | boolean | If `false`, store raw text without inference (default: `true`) |
| `immutable` | boolean | Prevents modification after creation |
| `expiration_date` | string | Auto-expiry date (`YYYY-MM-DD`) |
| `includes` | string | Preference filters for inclusion |
| `excludes` | string | Preference filters for exclusion |
| `async_mode` | boolean | Async processing (default: `true`). Set `false` to wait |

### Advanced Add Options

```python
# Immutable -- cannot be modified or overwritten
client.add(messages, user_id="alice", immutable=True)

# Expiring memory
client.add(messages, user_id="alice", expiration_date="2025-12-31")

# Selective extraction
client.add(messages, user_id="alice", includes="dietary preferences", excludes="payment info")

# Agent + session scoping
client.add(messages, user_id="alice", agent_id="nutrition-agent", run_id="session-456")

# Synchronous processing (wait for completion)
client.add(messages, user_id="alice", async_mode=False)

# Raw text -- skip LLM inference
client.add(
    [{"role": "user", "content": "User prefers dark mode."}],
    user_id="alice",
    infer=False,
)
```

---

## search() -- Find Memories

**Python:**
```python
results = client.search("dietary preferences?", user_id="alice")

# With filters and reranking
results = client.search(
    query="work experience",
    filters={"AND": [{"user_id": "alice"}, {"categories": {"contains": "professional_details"}}]},
    top_k=5,
    rerank=True,
    threshold=0.5
)

# With graph relations
results = client.search("colleagues", user_id="alice", enable_graph=True)

# Keyword search
results = client.search("vegetarian", user_id="alice", keyword_search=True)
```

**TypeScript:**
```typescript
const results = await client.search("dietary preferences", { user_id: "alice" });
const results = await client.search("work experience", {
    filters: { AND: [{ user_id: "alice" }, { categories: { contains: "professional_details" } }] },
    top_k: 5,
    rerank: true,
});
```

### Parameters

| Name | Type | Description |
|------|------|-------------|
| `query` | string | Natural language search query |
| `user_id` | string | Filter by user |
| `filters` | object | V2 filter object (AND/OR operators) |
| `top_k` | number | Number of results (default: 10) |
| `rerank` | boolean | Enable reranking for better relevance |
| `threshold` | number | Minimum similarity score (default: 0.3) |
| `keyword_search` | boolean | Use keyword-based search |
| `enable_graph` | boolean | Include graph relations |

### Common Filter Patterns

```python
# Single user (shorthand)
client.search("query", user_id="alice")

# OR across agents
filters={"OR": [{"user_id": "alice"}, {"agent_id": {"in": ["travel-agent", "sports-agent"]}}]}

# Category filtering (partial match)
filters={"AND": [{"user_id": "alice"}, {"categories": {"contains": "finance"}}]}

# Category filtering (exact match)
filters={"AND": [{"user_id": "alice"}, {"categories": {"in": ["personal_information"]}}]}

# Wildcard (match any non-null run)
filters={"AND": [{"user_id": "alice"}, {"run_id": "*"}]}

# Date range
filters={"AND": [
    {"user_id": "alice"},
    {"created_at": {"gte": "2024-01-01T00:00:00Z"}},
    {"created_at": {"lt": "2024-02-01T00:00:00Z"}}
]}

# Exclude categories with NOT
filters={"AND": [{"user_id": "user_123"}, {"NOT": {"categories": {"in": ["spam", "test"]}}}]}

# Multi-dimensional query
filters={"AND": [
    {"user_id": "user_123"},
    {"keywords": {"icontains": "invoice"}},
    {"categories": {"in": ["finance"]}},
    {"created_at": {"gte": "2024-01-01T00:00:00Z"}}
]}
```

---

## get() / getAll() -- Retrieve Memories

**Python:**
```python
# Single memory by ID
memory = client.get(memory_id="ea925981-...")

# All memories for a user
memories = client.get_all(filters={"AND": [{"user_id": "alice"}]})

# With date range
memories = client.get_all(
    filters={"AND": [
        {"user_id": "alex"},
        {"created_at": {"gte": "2024-07-01", "lte": "2024-07-31"}}
    ]}
)

# With graph data
memories = client.get_all(filters={"AND": [{"user_id": "alice"}]}, enable_graph=True)
```

**TypeScript:**
```typescript
const memory = await client.get("ea925981-...");
const memories = await client.getAll({ filters: { AND: [{ user_id: "alice" }] } });
```

**Note:** `get_all` requires at least one of `user_id`, `agent_id`, `app_id`, or `run_id` in filters.

---

## update() -- Modify Memories

**Python:**
```python
client.update(memory_id="ea925981-...", text="Updated: vegan since 2024")
client.update(memory_id="ea925981-...", text="Updated", metadata={"verified": True})
```

**TypeScript:**
```typescript
await client.update("ea925981-...", { text: "Updated: vegan since 2024" });
```

Cannot update immutable memories.

---

## delete() / deleteAll() -- Remove Memories

**Python:**
```python
client.delete(memory_id="ea925981-...")
client.delete_all(user_id="alice")  # Irreversible bulk delete
```

**TypeScript:**
```typescript
await client.delete("ea925981-...");
await client.deleteAll({ user_id: "alice" });
```

---

## history() -- Track Changes

**Python:**
```python
history = client.history(memory_id="ea925981-...")
# Returns: [{previous_value, new_value, action, timestamps}]
```

**TypeScript:**
```typescript
const history = await client.history("ea925981-...");
```

---

## Batch Operations (TypeScript)

```typescript
// Batch update
await client.batchUpdate([
    { memoryId: "uuid-1", text: "Updated text" },
    { memoryId: "uuid-2", text: "Another updated text" },
]);

// Batch delete
await client.batchDelete(["uuid-1", "uuid-2", "uuid-3"]);
```

---

## Additional Methods

```python
# List all users/agents/sessions with memories
users = client.users()

# Delete a user/agent entity
client.delete_users(user_id="alice")

# Submit feedback on a memory
client.feedback(memory_id="...", feedback="POSITIVE", feedback_reason="Accurate extraction")

# Export memories
export = client.create_memory_export(filters={"AND": [{"user_id": "alice"}]})
data = client.get_memory_export(memory_export_id=export["id"])
```

---

## Common Pitfalls

1. **Entity cross-filtering fails silently** -- `AND` with `user_id` + `agent_id` returns empty. Use `OR`.
2. **SQL operators rejected** -- use `gte`, `lt`, etc. Not `>=`, `<`.
3. **Metadata filtering is limited** -- only top-level keys with `eq`, `contains`, `ne`.
4. **Wildcard `*` excludes null** -- only matches non-null values.
5. **Default threshold is 0.3** -- increase for stricter matching.
6. **Async processing** -- memories process asynchronously. Wait 2-3s after `add()` before searching.
7. **Immutable memories** -- cannot be updated or deleted once created.

## Naming Conventions

Python uses `snake_case` (`user_id`, `memory_id`, `get_all`). TypeScript uses `camelCase` for methods (`getAll`, `deleteAll`, `batchUpdate`) but `snake_case` for API parameters (`user_id`, `agent_id`).
