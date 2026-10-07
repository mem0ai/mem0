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

**Constructor:** `MemoryClient(api_key=None, host=None, client=None)`. If `api_key` is not provided, reads from `MEM0_API_KEY` environment variable. Raises `ValueError` if no key found. `host` overrides the base URL and `client` accepts a custom `httpx.Client`. `MEM0_SOURCE`, `MEM0_APPLICATION` and `MEM0_CLIENT_STACK` set the request identity headers for wrappers.

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

#### add(messages, options=None, **kwargs)

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
| `agent_custom_instructions` | str | None | Extraction instructions for agent-scoped memories |
| `expiration_date` | str | None | `YYYY-MM-DD`, memory is hidden after this date |
| `timestamp` | int | None | Custom timestamp (Unix epoch seconds) |

**Returns:** `dict` -- asynchronous by default: `{"event_id": "...", "status": "PENDING"}`. Poll `GET /v1/event/{event_id}/` until `SUCCEEDED`. With `infer=False` it is synchronous and returns the stored `results`.

#### search(query, options=None, **kwargs)

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
| `threshold` | float | server-side | Relevance cutoff (0.0 to 1.0), applied before score blending, so it is not a floor on the returned `score`. The default and `0.0` returned the same or nearly the same results in live tests |
| `fields` | - | - | Not applied in v3 |
| `categories` | - | - | Not applied in v3. Use `filters={"AND": [{"categories": {"in": [...]}}]}` |
| `metadata` | - | - | Not applied in v3. Use `filters={"AND": [{"metadata": {...}}]}` |
| `reference_date` | str \| int | None | Anchor for relative time queries (`YYYY-MM-DD`, ISO datetime, or Unix epoch) |
| `show_expired` | bool | False | Include memories past their `expiration_date` |
| `latest_only` | bool | None | Only return the latest version of a memory |

**Returns:** `dict` -- `{"results": [{id, memory, user_id, categories, score, created_at, ...}]}`

#### get(memory_id)

Retrieve a single memory by ID.

```python
memory = client.get(memory_id="ea925981-...")
```

**Returns:** `dict` -- full memory object

#### get_all(options=None, **kwargs)

Retrieve all memories with optional filtering. Requires non-empty `filters`; scope them with at least one entity identifier.

```python
memories = client.get_all(filters={"user_id": "alice"})
# With compound filters
memories = client.get_all(filters={"AND": [{"user_id": "alice"}, {"categories": {"contains": "health"}}]})
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filters` | dict | None | Filter object with entity IDs and/or `AND`/`OR`/`NOT` conditions |
| `page` | int | 1 | Page number |
| `page_size` | int | 100 | Results per page (max 200) |
| `start_date` / `end_date` / `categories` | - | - | Not applied in v3. Use `filters` with `created_at` or `categories` |
| `show_expired` | bool | False | Include expired memories |
| `latest_only` | bool | None | Only return the latest version of a memory |

**Returns:** `dict` -- `{"count": int, "next": str | None, "previous": str | None, "results": [...]}`

#### update(memory_id, options=None, **kwargs)

Update a memory's `text`, `metadata`, `timestamp`, or `expiration_date` (pass `expiration_date=None` to clear it). At least one required.

```python
client.update("ea925981-...", text="Updated: vegan since 2024")
client.update("ea925981-...", metadata={"verified": True})
```

**Returns:** `dict` -- updated memory

#### delete(memory_id, delete_linked=False)

Permanently delete a single memory. With `delete_linked=True`, also deletes the older memories it superseded.

```python
client.delete("ea925981-...")
client.delete("ea925981-...", delete_linked=True)
```

#### delete_all(options=None, **kwargs)

Delete all memories matching the entity IDs (`user_id`, `agent_id`, `app_id`, `run_id`, passed as top-level kwargs). Irreversible.

```python
client.delete_all(user_id="alice")
```

#### history(memory_id)

Get the change history of a memory.

```python
history = client.history("ea925981-...")
# Returns: [{id, memory_id, input, old_memory, new_memory, event, user_id, categories, metadata, created_at, updated_at}]
```

---

### Batch Methods

#### batch_update(memories)

Update up to 1000 memories in a single request.

```python
client.batch_update([
    {"memory_id": "uuid-1", "text": "Updated text"},
    {"memory_id": "uuid-2", "text": "Another update"},
])
```

Each item must include `text`. `metadata` on a batch item is ignored and a metadata-only item returns a 400. Use `update(memory_id, metadata=...)` to change metadata.

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

Delete ALL users, agents, sessions, and memories. Complete data reset. It only deletes the entities on the first page returned by `users()`, so with many entities re-run it until it raises `No entities to delete`, or delete per entity with `delete_users(user_id=...)`.

```python
client.reset()
```

---

### Export & Summary

#### create_memory_export(schema, **kwargs)

Create a structured export of memories.

```python
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "preferences": {"type": "array", "items": {"type": "string"}},
    }
}
export = client.create_memory_export(schema=schema, filters={"AND": [{"user_id": "alice"}]})
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

### User Profiles

```python
profile = client.get_profile("alice")
client.generate_profile("alice")
client.get_profile_settings()
client.update_profile_settings(enabled=True)
```

`get_profile` returns `status` (`succeeded`, `pending`, `failed`, `not_enabled`, `insufficient_data`) plus `profile`; generation is asynchronous, so branch on `status`. Other methods: `sample_profiles(limit=None)` and `get_profile_job(job_id_or_status_url)`.

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
client.update_webhook(webhook_id="wh_123", name="Updated", url="https://new-url.com")

# Delete
client.delete_webhook(webhook_id="wh_123")
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
    agent_custom_instructions="Extract only what the agent learned about the user",
    multilingual=True,
    decay=True,
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
pip install "mem0ai[nlp]"      # optional: spaCy entity linking (Python 3.10-3.12)
pip install "mem0ai[extras]"   # optional: fastembed for Qdrant BM25 keyword search
```

### Memory Class

```python
from mem0 import Memory

m = Memory()  # Defaults: OpenAI gpt-5-mini + text-embedding-3-small, local Qdrant at /tmp/qdrant
```

`Memory(config)` takes a `MemoryConfig` object. For a plain dict use `Memory.from_config(config)`. Requires `OPENAI_API_KEY` for the default LLM and embedder.

**Import:** `from mem0 import Memory` (NOT `MemoryClient` -- that is the Platform client)

### Configuration

```python
config = {
    "llm": {
        "provider": "openai",        # openai, anthropic, gemini, groq, ollama, lmstudio, azure_openai, aws_bedrock, together, deepseek, xai, vllm, litellm, ...
        "config": {
            "model": "gpt-5-mini",
            "api_key": "sk-xxx",
        }
    },
    "embedder": {
        "provider": "openai",        # openai, ollama, azure_openai, lmstudio, gemini, vertexai, huggingface, fastembed, aws_bedrock, together
        "config": {
            "model": "text-embedding-3-small",
            "api_key": "sk-xxx",
        }
    },
    "vector_store": {
        "provider": "qdrant",        # qdrant (default), chroma, pgvector, pinecone, milvus, redis, supabase, faiss, azure_ai_search, ...
        "config": {
            "collection_name": "my_memories",
            "host": "localhost",
            "port": 6333,
        }
    },
    "history_db_path": "history.db",              # SQLite path for change history (default ~/.mem0/history.db)
    "custom_instructions": "...",                  # Custom LLM prompt for extraction
}

m = Memory.from_config(config)
```

### Context Manager

```python
with Memory.from_config(config) as m:
    m.add("I prefer dark mode", user_id="alice")
    results = m.search("preferences", filters={"user_id": "alice"})
# SQLite connections released automatically
```

### Methods

All methods mirror the Platform client but run locally:

#### add(messages, *, user_id, agent_id, run_id, metadata, expiration_date, infer=True, memory_type, prompt)

```python
m.add("I'm a vegetarian", user_id="alice")
m.add([
    {"role": "user", "content": "I like hiking"},
    {"role": "assistant", "content": "Great outdoor activity!"}
], user_id="alice")
```

At least one of `user_id`, `agent_id`, `run_id` required.

`timestamp` raises `ValueError` in OSS (Platform only).

**Returns:** `{"results": [{"id": "...", "memory": "...", "event": "ADD"}]}`

#### search(query, *, top_k=20, filters=None, threshold=0.1, rerank=False, explain=False, show_expired=False)

```python
results = m.search("dietary preferences", filters={"user_id": "alice"}, top_k=5)
```

Entity IDs (`user_id`, `agent_id`, `run_id`) must be passed inside the `filters` dict.

Supports filter operators: `eq`, `ne`, `in`, `nin`, `gt`, `gte`, `lt`, `lte`, `contains`, `icontains`, plus `AND` / `OR` / `NOT`. `reference_date` raises `ValueError` in OSS (Platform only).

#### get(memory_id) / get_all(*, filters, top_k=20, show_expired=False) / update(memory_id, text=None, metadata=None, expiration_date) / delete(memory_id) / delete_all(user_id=None, agent_id=None, run_id=None) / history(memory_id)

`get_all()` requires entity IDs inside `filters` and returns `{"results": [...]}`. `update()` takes `text` (`data` is a deprecated alias) and needs at least one of `text`, `metadata`, `expiration_date`. `delete_all()` needs at least one entity ID and takes them top-level. `m.project.update()` raises `ValueError` in OSS.

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

m = AsyncMemory.from_config(config)
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

The "v2" line is Python SDK 1.x (TypeScript SDK 2.x). If you are still on it, these are the differences from Python 2.x:

**API Changes:**
- **Entity IDs in search/get_all:** `user_id`, `agent_id` were top-level kwargs, now they go inside `filters` (top-level raises `ValueError`)
  ```python
  # v2
  results = client.search("query", user_id="alice")
  # v3
  results = client.search("query", filters={"user_id": "alice"})
  ```
- **add() returns:** v2 returns ADD, UPDATE, DELETE events; v3 returns ADD only
- **Platform add() is async:** returns `{"event_id": "...", "status": "PENDING"}`

**Default Changes:**
| Param | v2 Platform | v3 Platform | v2 OSS | v3 OSS |
|-------|-------------|-------------|--------|--------|
| `top_k` | 10 | 10 | 100 | 20 |
| `threshold` | 0.3 | server-side cutoff | None | 0.1 |
| `rerank` | False | False | True | False |

**Removed Parameters:**
- Constructor: `org_id`, `project_id`
- add(): `async_mode`, `output_format`, `enable_graph`, `immutable`, `filter_memories`, `batch_size`, `force_add_only`, `includes`, `excludes`, `keyword_search`
- search()/get_all(): `enable_graph`
- Config: `enable_graph`, `graph_store`, `custom_fact_extraction_prompt` (renamed to `custom_instructions`), `custom_update_memory_prompt` (deprecated)

`expiration_date` is still supported on `add()` and `update()`.

**Graph memory:** the external graph store (Neo4j, Memgraph, Kuzu, AGE) was removed from OSS. Entity linking is built in (spaCy via `mem0ai[nlp]`, stored in a `{collection}_entities` vector collection) and falls back to semantic-only search without it.

See the [v2 to v3 migration guide](https://docs.mem0.ai/migration/oss-v2-to-v3) for full details.
