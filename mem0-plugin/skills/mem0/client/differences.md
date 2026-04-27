# Python vs TypeScript SDK Differences

Quick-reference cheatsheet for developers working across both Mem0 SDKs.

## Constructor

| Aspect | Python | TypeScript |
|--------|--------|------------|
| Import (Platform) | `from mem0 import MemoryClient` | `import MemoryClient from 'mem0ai'` |
| Import (OSS) | `from mem0 import Memory` | `import { Memory } from 'mem0ai/oss'` |
| Constructor | `MemoryClient(api_key="m0-xxx")` | `new MemoryClient({ apiKey: 'm0-xxx' })` |
| Required param | `api_key` (positional or kwarg) | `apiKey` (in options object) |

Both read from `MEM0_API_KEY` env var if no key provided.

## Method Naming

| Operation | Python | TypeScript |
|-----------|--------|------------|
| Add | `add()` | `add()` |
| Search | `search()` | `search()` |
| Get | `get()` | `get()` |
| Get all | `get_all()` | `getAll()` |
| Update | `update()` | `update()` |
| Delete | `delete()` | `delete()` |
| Delete all | `delete_all()` | `deleteAll()` |
| History | `history()` | `history()` |
| Batch update | `batch_update()` | `batchUpdate()` |
| Batch delete | `batch_delete()` | `batchDelete()` |
| List users | `users()` | `users()` |
| Delete users | `delete_users()` | `deleteUsers()` |
| Get project | `project.get()` | `getProject()` |
| Update project | `project.update()` | `updateProject()` |
| Create webhook | `create_webhook()` | `createWebhook()` |
| Get webhooks | `get_webhooks()` | `getWebhooks()` |
| Update webhook | `update_webhook()` | `updateWebhook()` |
| Delete webhook | `delete_webhook()` | `deleteWebhook()` |
| Create export | `create_memory_export()` | `createMemoryExport()` |
| Get export | `get_memory_export()` | `getMemoryExport()` |
| Feedback | `feedback()` | `feedback()` |

**Rule:** Python uses `snake_case`, TypeScript uses `camelCase` for method names.

## Parameter Passing

```python
# Python: kwargs
client.add(messages, user_id="alice", metadata={"source": "chat"})
client.search("query", filters={"user_id": "alice"}, top_k=5, rerank=True)
```

```typescript
// TypeScript: options object with camelCase for top-level params, snake_case for filter keys
await client.add(messages, { userId: 'alice', metadata: { source: 'chat' } });
await client.search('query', { filters: { user_id: 'alice' }, topK: 5, rerank: true });
```

**v3:** Python uses `snake_case` everywhere. TypeScript uses `camelCase` for top-level params (`userId`, `topK`) but `snake_case` for filter keys (`user_id`, `agent_id`).

## Architectural Differences

| Aspect | Python | TypeScript |
|--------|--------|------------|
| HTTP library | httpx | axios |
| Default timeout | 300s | 60s |
| Sync support | Yes (`MemoryClient`) | No (all async) |
| Async support | Yes (`AsyncMemoryClient`) | All methods are async |
| Project management | `client.project.*` (separate class) | `client.getProject()` / `client.updateProject()` |
| Context manager | `async with AsyncMemoryClient()` | Not supported |

## Platform Features: Python-only

These methods exist in Python but not TypeScript:

| Method | Description |
|--------|-------------|
| `get_summary(filters)` | Get summary of memories |
| `reset()` | Delete ALL data (users + memories) |
| `project.create(name)` | Create a new project |
| `project.delete()` | Delete current project |
| `project.get_members()` | List project members |
| `project.add_member(email, role)` | Add member to project |
| `project.update_member(email, role)` | Change member role |
| `project.remove_member(email)` | Remove member |

## Platform Features: TypeScript-only

| Method | Description |
|--------|-------------|
| `deleteUser(data)` | Convenience method for single entity deletion |
| `ping()` | Health check endpoint |

## OSS Config Naming

| Python config key | TypeScript config key |
|-------------------|----------------------|
| `vector_store` | `vectorStore` |
| `history_db_path` | `historyDbPath` |
| `custom_instructions` | `customInstructions` |

## OSS Scope Parameter Naming

| Python | TypeScript |
|--------|------------|
| `user_id="alice"` | `userId: 'alice'` |
| `agent_id="bot"` | `agentId: 'bot'` |
| `run_id="session"` | `runId: 'session'` |

## Entity ID Passing (v3)

| Method | Python | TypeScript |
|--------|--------|------------|
| add() | Top-level: `user_id="alice"` | Top-level: `{ userId: 'alice' }` |
| search() | In filters: `filters={"user_id": "alice"}` | In filters: `{ filters: { user_id: 'alice' } }` |
| get_all() | In filters: `filters={"user_id": "alice"}` | In filters: `{ filters: { user_id: 'alice' } }` |

## Common Gotcha

When searching/filtering, both Python and TypeScript use `snake_case` for filter keys. TypeScript only uses `camelCase` for top-level method parameters:

```python
# Python - snake_case in filters
results = client.search("query", filters={"user_id": "alice"})
```

```typescript
// TypeScript - snake_case in filters, camelCase for top-level params
const results = await client.search('query', { filters: { user_id: 'alice' }, topK: 20 });
```
