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
client.search("query", user_id="alice", top_k=5, rerank=True)
```

```typescript
// TypeScript: options object
await client.add(messages, { user_id: 'alice', metadata: { source: 'chat' } });
await client.search('query', { user_id: 'alice', top_k: 5, rerank: true });
```

**Important:** Both use `snake_case` for API parameter names (`user_id`, `agent_id`, `top_k`, etc.). Only method names differ.

Exception: OSS TypeScript uses `camelCase` for config params (`userId`, `agentId`, `runId`).

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
| `graph_store` | `graphStore` |
| `history_db_path` | `historyDbPath` |
| `custom_instructions` | `customInstructions` |
| `enable_graph` | `enableGraph` |

## OSS Scope Parameter Naming

| Python | TypeScript |
|--------|------------|
| `user_id="alice"` | `userId: 'alice'` |
| `agent_id="bot"` | `agentId: 'bot'` |
| `run_id="session"` | `runId: 'session'` |

## Common Gotcha

When searching/filtering, **both SDKs use `snake_case`** for filter keys:

```python
# Python
filters = {"AND": [{"user_id": "alice"}, {"categories": {"contains": "health"}}]}
```

```typescript
// TypeScript -- same snake_case in filter objects!
const filters = { AND: [{ user_id: 'alice' }, { categories: { contains: 'health' } }] };
```
