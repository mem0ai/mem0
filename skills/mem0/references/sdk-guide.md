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

Constructor accepts `apiKey` (required in TypeScript; Python falls back to the `MEM0_API_KEY` env var) and `host` (optional, default: `https://api.mem0.ai`).

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
```

**TypeScript:**
```typescript
await client.add(messages, { userId: "alice" });
await client.add(messages, { userId: "alice", metadata: { source: "onboarding" } });
```

### Parameters

| Name | Type | Description |
|------|------|-------------|
| `messages` | array | `[{"role": "user", "content": "..."}]` |
| `user_id` | string | User identifier (recommended) |
| `agent_id` | string | Agent identifier |
| `run_id` | string | Session identifier |
| `metadata` | object | Custom key-value pairs |
| `infer` | boolean | If `false`, store raw text without inference (default: `true`) |
| `expiration_date` | string | `YYYY-MM-DD`, memory is hidden from search and get_all after this date |

### Advanced Add Options

```python
# Agent + session scoping
client.add(messages, user_id="alice", agent_id="nutrition-agent", run_id="session-456")

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
results = client.search("dietary preferences?", filters={"user_id": "alice"})

# With filters and reranking
results = client.search(
    query="work experience",
    filters={"AND": [{"user_id": "alice"}, {"categories": {"contains": "professional_details"}}]},
    top_k=5,
    rerank=True,
    threshold=0.5
)
```

**TypeScript:**
```typescript
const results = await client.search("dietary preferences", { filters: { user_id: "alice" } });
const results = await client.search("work experience", {
    filters: { AND: [{ user_id: "alice" }, { categories: { contains: "professional_details" } }] },
    topK: 5,
    rerank: true,
});
```

### Parameters

| Name | Type | Description |
|------|------|-------------|
| `query` | string | Natural language search query |
| `filters` | object | Filter object (AND/OR operators). Use `{"user_id": "..."}` to filter by user |
| `top_k` | number | Number of results (default: 10 for Platform) |
| `rerank` | boolean | Enable reranking for better relevance (default: `false`) |
| `threshold` | number | Server-side relevance cutoff (0 to 1), applied before score blending, so it is not a floor on the returned `score`. The default and `0.0` returned the same or nearly the same results in live tests |
| `reference_date` | string / number | Anchor for relative time queries such as "last week" (epoch, `YYYY-MM-DD`, or ISO datetime) |
| `show_expired` | boolean | Include memories past their `expiration_date` (default: `false`) |
| `latest_only` | boolean | Only return the latest version of a memory |

### Common Filter Patterns

**Python:**
```python
# Single user filter
filters={"user_id": "alice"}

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
filters={"AND": [{"user_id": "user_123"}, {"NOT": [{"categories": {"in": ["spam", "test"]}}]}]}

# Multi-dimensional query
filters={"AND": [
    {"user_id": "user_123"},
    {"categories": {"in": ["finance"]}},
    {"created_at": {"gte": "2024-01-01T00:00:00Z"}}
]}
```

**TypeScript:**
```typescript
// Single user filter
filters: { user_id: "alice" }

// OR across agents
filters: { OR: [{ user_id: "alice" }, { agent_id: { in: ["travel-agent", "sports-agent"] } }] }

// Category filtering (partial match)
filters: { AND: [{ user_id: "alice" }, { categories: { contains: "finance" } }] }

// Category filtering (exact match)
filters: { AND: [{ user_id: "alice" }, { categories: { in: ["personal_information"] } }] }
```

---

## get() / getAll() -- Retrieve Memories

**Python:**
```python
# Single memory by ID
memory = client.get(memory_id="ea925981-...")

# All memories for a user
memories = client.get_all(filters={"user_id": "alice"})

# With date range
memories = client.get_all(
    filters={"AND": [
        {"user_id": "alex"},
        {"created_at": {"gte": "2024-07-01", "lte": "2024-07-31"}}
    ]}
)
```

**TypeScript:**
```typescript
const memory = await client.get("ea925981-...");
const memories = await client.getAll({ filters: { user_id: "alice" } });
```

**Note:** `get_all` requires non-empty `filters`. Scope them with at least one of `user_id`, `agent_id`, `app_id`, or `run_id`.

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

---

## delete() / deleteAll() -- Remove Memories

**Python:**
```python
client.delete(memory_id="ea925981-...")
client.delete(memory_id="ea925981-...", delete_linked=True)
client.delete_all(user_id="alice")  # Irreversible bulk delete
```

**TypeScript:**
```typescript
await client.delete("ea925981-...");
await client.delete("ea925981-...", { deleteLinked: true });
await client.deleteAll({ userId: "alice" });
```

---

## history() -- Track Changes

**Python:**
```python
history = client.history(memory_id="ea925981-...")
# Returns: [{id, memory_id, input, old_memory, new_memory, event, user_id, categories, metadata, created_at, updated_at}]
```

**TypeScript:**
```typescript
const history = await client.history("ea925981-...");
```

---

## Batch Operations

**Python:**
```python
client.batch_update([
    {"memory_id": "uuid-1", "text": "Updated text"},
    {"memory_id": "uuid-2", "text": "Another updated text"},
])

client.batch_delete([{"memory_id": "uuid-1"}, {"memory_id": "uuid-2"}])
```

**TypeScript:**
```typescript
// Batch update
await client.batchUpdate([
    { memoryId: "uuid-1", text: "Updated text" },
    { memoryId: "uuid-2", text: "Another updated text" },
]);

// Batch delete
await client.batchDelete(["uuid-1", "uuid-2", "uuid-3"]);
```

Each batch update item must include `text`. `metadata` on an item is ignored and a metadata-only item returns a 400.

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
export = client.create_memory_export(
    schema={"type": "object", "properties": {"diet": {"type": "string"}}},
    filters={"AND": [{"user_id": "alice"}]},
)
data = client.get_memory_export(memory_export_id=export["id"])

profile = client.get_profile("alice")
client.generate_profile("alice")
```

---

## Common Pitfalls

1. **Entity cross-filtering fails silently** -- `AND` with `user_id` + `agent_id` returns empty. Use `OR`.
2. **SQL operators rejected** -- use `gte`, `lt`, etc. Not `>=`, `<`.
3. **Metadata filtering is limited** -- only top-level keys with `eq`, `contains`, `ne`.
4. **Wildcard `*` excludes null** -- only matches non-null values.
5. **Threshold is a server-side cutoff** -- raise it to drop weak matches, but it is applied before score blending, so it is not a floor on the returned `score`. Filter on `score` client-side for a precise cutoff.
6. **Async processing** -- `add()` returns `{"event_id": ..., "status": "PENDING"}` (`eventId` on the TS client). Memories are searchable after the event is `SUCCEEDED` (poll `GET /v1/event/{event_id}/`, or wait a few seconds). `infer=False` is synchronous.

## Naming Conventions

Python uses `snake_case` everywhere (`user_id`, `memory_id`, `get_all`). TypeScript uses `camelCase` for methods (`getAll`, `deleteAll`, `batchUpdate`) and top-level parameters (`userId`, `topK`, `pageSize`), but filter keys use `snake_case` (`user_id`, `agent_id`).

---

## v2 to v3 Migration

### Breaking Changes in v3

**1. Entity IDs in search() and getAll()**

v3 requires entity IDs (`user_id`, `agent_id`, `run_id`) inside `filters` instead of as top-level parameters:

```python
# v2 (deprecated)
client.search("query", user_id="alice")
client.get_all(user_id="alice")

# v3
client.search("query", filters={"user_id": "alice"})
client.get_all(filters={"user_id": "alice"})
```

```typescript
// v2 (deprecated)
await client.search("query", { user_id: "alice" });
await client.getAll({ user_id: "alice" });

// v3
await client.search("query", { filters: { user_id: "alice" } });
await client.getAll({ filters: { user_id: "alice" } });
```

**2. TypeScript Parameter Naming**

v3 TypeScript uses camelCase for all parameters:

| v2 | v3 |
|----|-----|
| `user_id` | `userId` |
| `agent_id` | `agentId` |
| `run_id` | `runId` |
| `top_k` | `topK` |
| `page_size` | `pageSize` |

**3. Default Values Changed**

| Parameter | v2 Default | v3 Default |
|-----------|------------|------------|
| `threshold` | 0.3 | server-side cutoff |
| `rerank` | `false` | `false` |

**4. Removed Parameters**

The following parameters are no longer supported:

| Parameter | Status |
|-----------|--------|
| `enable_graph` | Removed from add/search/getAll |
| `keyword_search` | Removed from search |
| `filter_memories` | Removed |
| `immutable` | Removed from add |
| `includes` | Removed from add |
| `excludes` | Removed from add |
| `async_mode` | Removed from add |
