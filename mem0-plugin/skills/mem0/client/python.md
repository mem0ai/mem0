# Mem0 Python SDK Reference

Complete reference for the `mem0ai` Python package. Covers both the Platform client (managed API) and the Open Source self-hosted variant.

---

## Platform Client

### Installation

```bash
pip install mem0ai
export MEM0_API_KEY="m0-your-api-key"
```

### MemoryClient (Synchronous)

```python
from mem0 import MemoryClient

client = MemoryClient(api_key="m0-xxx")
```

**Constructor:** `MemoryClient(api_key=None)`. If `api_key` is not provided, reads from `MEM0_API_KEY` environment variable. Raises `ValueError` if no key found.

- HTTP library: `httpx`
- Timeout: 300 seconds
- Base URL: `https://api.mem0.ai`

### AsyncMemoryClient (Asynchronous)

```python
from mem0 import AsyncMemoryClient

client = AsyncMemoryClient(api_key="m0-xxx")

# Or use as context manager
async with AsyncMemoryClient(api_key="m0-xxx") as client:
    results = await client.search("query", filters={"user_id": "alice"})
```

Same methods as `MemoryClient`, all `async`/`await`. Supports async context manager.

---

### Memory Methods

#### add(messages, **kwargs)

Store new memories from messages.

```python
messages = [
    {"role": "user", "content": "I'm a vegetarian and allergic to nuts."},
    {"role": "assistant", "content": "Got it! I'll remember that."}
]
client.add(messages, user_id="alice")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `messages` | str \| dict \| list[dict] | required | Message content. Strings auto-convert to user messages |
| `user_id` | str | None | User identifier |
| `agent_id` | str | None | Agent identifier |
| `app_id` | str | None | Application identifier |
| `run_id` | str | None | Session/run identifier |
| `metadata` | dict | None | Custom key-value pairs |
| `infer` | bool | True | If False, store raw text without LLM inference |
| `custom_categories` | list | None | Override project categories |
| `custom_instructions` | str | None | Override extraction instructions |
| `timestamp` | int \| float \| str | None | Custom timestamp (Unix epoch or ISO 8601) |

**Returns:** `dict` -- list of events: `[{"id": "...", "event": "ADD", "data": {"memory": "..."}}]`

#### search(query, **kwargs)

Search memories by semantic similarity.

```python
results = client.search("dietary preferences", filters={"user_id": "alice"})
for mem in results.get("results", []):
    print(mem["memory"], mem["score"])
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | str | required | Natural language search query |
| `filters` | dict | None | Filter object with entity IDs and/or `AND`/`OR`/`NOT` conditions (e.g., `{"user_id": "alice"}`) |
| `top_k` | int | 10 | Number of results |
| `rerank` | bool | False | Enable deep semantic reranking (+150-200ms) |
| `threshold` | float | 0.1 | Minimum similarity score |
| `fields` | list | None | Specific fields to return |
| `categories` | list | None | Filter by category |

**Returns:** `dict` -- `{"results": [{id, memory, user_id, categories, score, created_at, ...}]}`

#### get(memory_id)

Retrieve a single memory by ID.

```python
memory = client.get(memory_id="ea925981-...")
```

**Returns:** `dict` -- full memory object

#### get_all(**kwargs)

Retrieve all memories with optional filtering. Requires at least one entity identifier.

```python
memories = client.get_all(filters={"user_id": "alice"})
# With compound filters
memories = client.get_all(filters={"AND": [{"user_id": "alice"}, {"categories": {"contains": "health"}}]})
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filters` | dict | None | Filter object with entity IDs and/or `AND`/`OR`/`NOT` conditions |
| `top_k` | int | None | Limit results |
| `page` | int | None | Page number |
| `page_size` | int | None | Results per page |

**Returns:** `dict` -- `{"results": [...]}`

#### update(memory_id, text=None, metadata=None, timestamp=None)

Update a memory's content, metadata, or timestamp. At least one parameter required.

```python
client.update("ea925981-...", text="Updated: vegan since 2024")
client.update("ea925981-...", metadata={"verified": True})
```

**Returns:** `dict` -- updated memory

#### delete(memory_id)

Permanently delete a single memory.

```python
client.delete("ea925981-...")
```

#### delete_all(**kwargs)

Delete all memories matching filters. Irreversible.

```python
client.delete_all(user_id="alice")
```

#### history(memory_id)

Get the change history of a memory.

```python
history = client.history("ea925981-...")
# Returns: [{previous_value, new_value, action, timestamps}]
```

---

### Batch Methods

#### batch_update(memories)

Update up to 1000 memories in a single request.

```python
client.batch_update([
    {"memory_id": "uuid-1", "text": "Updated text"},
    {"memory_id": "uuid-2", "text": "Another update", "metadata": {"verified": True}},
])
```

#### batch_delete(memories)

Delete up to 1000 memories in a single request.

```python
client.batch_delete([
    {"memory_id": "uuid-1"},
    {"memory_id": "uuid-2"},
])
```

---

### User/Entity Management

#### users()

List all users, agents, and sessions that have memories.

```python
users = client.users()
# Returns: {"results": [{"type": "user", "name": "alice"}, ...]}
```

#### delete_users(user_id=None, agent_id=None, app_id=None, run_id=None)

Delete a specific entity and all its memories.

```python
client.delete_users(user_id="alice")
```

#### reset()

Delete ALL users, agents, sessions, and memories. Complete data reset.

```python
client.reset()
```

---

### Export & Summary

#### create_memory_export(schema, **kwargs)

Create a structured export of memories.

```python
import json

schema = json.dumps({
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "preferences": {"type": "array", "items": {"type": "string"}},
    }
})
export = client.create_memory_export(schema=schema, user_id="alice")
```

#### get_memory_export(**kwargs)

Retrieve a previously created export.

```python
result = client.get_memory_export(memory_export_id=export["id"])
```

#### get_summary(filters=None)

Get a summary of memories.

```python
summary = client.get_summary(filters={"user_id": "alice"})
```

---

### Feedback

#### feedback(memory_id, feedback=None, feedback_reason=None)

Provide quality feedback on a memory.

```python
client.feedback(
    memory_id="mem-123",
    feedback="POSITIVE",  # POSITIVE | NEGATIVE | VERY_NEGATIVE | None (clear)
    feedback_reason="Accurately captured preference"
)
```

---

### Webhooks

```python
# List
webhooks = client.get_webhooks(project_id="proj_123")

# Create
webhook = client.create_webhook(
    url="https://your-app.com/webhook",
    name="Memory Logger",
    project_id="proj_123",
    event_types=["memory_add", "memory_update"]
)

# Update
client.update_webhook(webhook_id=123, name="Updated", url="https://new-url.com")

# Delete
client.delete_webhook(webhook_id=123)
```

---

### Project Management

Access via `client.project.*`:

```python
# Get project config
config = client.project.get(fields=["custom_categories", "custom_instructions"])

# Update project settings
client.project.update(
    custom_instructions="Extract dietary preferences and health info",
    custom_categories=[{"health": "Medical and dietary info"}],
    multilingual=True,
)

# Create/delete project
client.project.create(name="My Project", description="...")
client.project.delete()

# Member management
members = client.project.get_members()
client.project.add_member(email="user@example.com", role="READER")  # READER or OWNER
client.project.update_member(email="user@example.com", role="OWNER")
client.project.remove_member(email="user@example.com")
```

---

## Open Source / Self-Hosted

### Installation

```bash
pip install mem0ai
```

### Memory Class

```python
from mem0 import Memory

m = Memory()  # Uses default config (OpenAI embedder + in-memory vector store)
```

**Import:** `from mem0 import Memory` (NOT `MemoryClient` -- that is the Platform client)

### Configuration

```python
config = {
    "llm": {
        "provider": "openai",        # openai, groq, azure, ollama, lmstudio, google, anthropic, mistral
        "config": {
            "model": "gpt-5-mini",
            "api_key": "sk-xxx",
        }
    },
    "embedder": {
        "provider": "openai",        # openai, ollama, azure, lmstudio, google, huggingface
        "config": {
            "model": "text-embedding-3-small",
            "api_key": "sk-xxx",
        }
    },
    "vector_store": {
        "provider": "qdrant",        # faiss, qdrant, pgvector, redis, supabase, azure_ai_search, memory
        "config": {
            "collection_name": "my_memories",
            "host": "localhost",
            "port": 6333,
        }
    },
    "history_db_path": "history.db",              # SQLite path for change history
    "custom_instructions": "...",                  # Custom LLM prompt for extraction
}

m = Memory.from_config(config)
```

### Context Manager

```python
with Memory(config) as m:
    m.add("I prefer dark mode", user_id="alice")
    results = m.search("preferences", filters={"user_id": "alice"})
# SQLite connections released automatically
```

### Methods

All methods mirror the Platform client but run locally:

#### add(messages, *, user_id, agent_id, run_id, metadata, infer=True)

```python
m.add("I'm a vegetarian", user_id="alice")
m.add([
    {"role": "user", "content": "I like hiking"},
    {"role": "assistant", "content": "Great outdoor activity!"}
], user_id="alice")
```

At least one of `user_id`, `agent_id`, `run_id` required.

**Returns:** `{"results": [...], "relations": [...]}`

#### search(query, *, filters=None, top_k=20, threshold=0.1, rerank=False)

```python
results = m.search("dietary preferences", filters={"user_id": "alice"}, top_k=5)
```

Entity IDs (`user_id`, `agent_id`, `run_id`) must be passed inside the `filters` dict.

Supports filter operators: `eq`, `ne`, `in`, `nin`, `gt`, `gte`, `lt`, `lte`, `contains`, `not_contains`.

#### get(memory_id) / get_all(**kwargs) / update(memory_id, data, metadata=None) / delete(memory_id) / delete_all(**kwargs) / history(memory_id)

Same interface as Platform client.

#### reset()

Clear the entire vector store collection and history database. Recreates the vector store.

```python
m.reset()
```

#### close()

Release SQLite connections. Called automatically when using context manager.

### AsyncMemory

```python
from mem0 import AsyncMemory

m = AsyncMemory(config)
await m.add("text", user_id="alice")
results = await m.search("query", filters={"user_id": "alice"})
```

---

## Key Differences: Platform vs OSS

| Aspect | Platform (`MemoryClient`) | OSS (`Memory`) |
|--------|--------------------------|----------------|
| **Import** | `from mem0 import MemoryClient` | `from mem0 import Memory` |
| **Auth** | API key required (`MEM0_API_KEY`) | No API key -- config-based |
| **Execution** | API calls to `api.mem0.ai` | Local execution |
| **Infrastructure** | Fully managed | Self-managed vector DB, embedder, LLM |
| **Entity filtering** | `filters={"user_id": "..."}` | `filters={"user_id": "..."}` |
| **Batch ops** | `batch_update`, `batch_delete` | Not available |
| **Webhooks** | Full CRUD | Not available |
| **Export** | `create_memory_export`, `get_memory_export` | Not available |
| **Feedback** | `feedback()` | Not available |
| **Project mgmt** | `client.project.*` | Not available |
| **User listing** | `users()`, `delete_users()` | Not available |
| **Custom prompts** | Via project settings | Direct config (`custom_instructions`) |
| **History** | Platform-managed | SQLite (configurable) |
| **Async** | `AsyncMemoryClient` | `AsyncMemory` |

---

## v2 Compatibility

If you're using SDK v2.x or the v2 API:

**API Changes:**
- **Entity IDs in search/get_all:** Pass `user_id`, `agent_id` as top-level kwargs instead of inside `filters`
  ```python
  # v2
  results = client.search("query", user_id="alice")
  # v3
  results = client.search("query", filters={"user_id": "alice"})
  ```
- **add() returns:** v2 returns ADD, UPDATE, DELETE events; v3 returns ADD only

**Default Changes:**
| Param | v2 | v3 |
|-------|----|----|
| `top_k` | 100 | 20 |
| `threshold` | None | 0.1 |
| `rerank` | True | False |

**Removed Parameters:**
- Constructor: `org_id`, `project_id`
- add(): `async_mode`, `output_format`, `enable_graph`, `immutable`, `expiration_date`, `filter_memories`, `batch_size`, `force_add_only`, `includes`, `excludes`, `keyword_search`
- search()/get_all(): `enable_graph`
- Config: `enable_graph`, `graph_store`, `custom_fact_extraction_prompt` (renamed to `custom_instructions`)

See the [v2 to v3 migration guide](https://docs.mem0.ai/migration/oss-v2-to-v3) for full details.
