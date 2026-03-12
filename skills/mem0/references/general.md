# Mem0 Platform -- General Concepts

## Table of Contents
- [What Mem0 Does](#what-mem0-does)
- [Core Memory Operations](#core-memory-operations)
- [SDK Initialization](#sdk-initialization)
- [Endpoint Summary](#endpoint-summary)
- [Memory Object Structure](#memory-object-structure)
- [Processing Model](#processing-model)
- [Scoping Identifiers](#scoping-identifiers)

## What Mem0 Does

Mem0 is a universal, self-improving memory layer for LLM applications. It provides:

- **Memory persistence** across users and agents -- conversations maintain context
- **Automatic inference** -- extracts structured memories from conversation messages
- **Semantic search** -- find relevant memories by natural language query
- **Graph relationships** -- entity-level connections between memories (Pro plan)
- **Prompt reduction** -- eliminates repeated context by retrieving relevant memories

The Platform is a fully managed hosted service. Infrastructure (vector stores, graph services, rerankers) is handled internally.

## Core Memory Operations

| Operation | Description | Detailed Reference |
|-----------|-------------|-------------------|
| **Add** | Store new memories from conversation messages | [add-memory.md](add-memory.md) |
| **Search** | Find memories by semantic query with filters | [search-memory.md](search-memory.md) |
| **Get** | Retrieve a specific memory by ID or list all | [update-delete.md](update-delete.md) |
| **Update** | Modify text or metadata of existing memory | [update-delete.md](update-delete.md) |
| **Delete** | Remove a specific memory or all memories | [update-delete.md](update-delete.md) |

## SDK Initialization

**Python:**
```python
from mem0 import MemoryClient
client = MemoryClient(api_key="your-api-key")
```

**Python (Async):**
```python
from mem0 import AsyncMemoryClient
client = AsyncMemoryClient(api_key="your-api-key")
```

**JavaScript:**
```javascript
import MemoryClient from 'mem0ai';
const client = new MemoryClient({ apiKey: 'your-api-key' });
```

**With org/project scope:**
```python
client = MemoryClient(
    api_key="your-api-key",
    org_id="your-org-id",
    project_id="your-project-id"
)
```

## Endpoint Summary

| Operation | Method | URL |
|-----------|--------|-----|
| Add Memories | `POST` | `/v1/memories/` |
| Search Memories | `POST` | `/v2/memories/search/` |
| Get All Memories | `POST` | `/v2/memories/` |
| Get Single Memory | `GET` | `/v1/memories/{memory_id}/` |
| Update Memory | `PUT` | `/v1/memories/{memory_id}/` |
| Delete Memory | `DELETE` | `/v1/memories/{memory_id}/` |

Base URL: `https://api.mem0.ai`

All endpoints require: `Authorization: Token <MEM0_API_KEY>`

## Memory Object Structure

A memory record contains:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (UUID) | Unique memory identifier |
| `memory` | string | Text content of the memory |
| `user_id` | string | Associated user |
| `agent_id` | string (nullable) | Agent identifier |
| `app_id` | string (nullable) | Application identifier |
| `run_id` | string (nullable) | Run/session identifier |
| `metadata` | object | Custom key-value pairs |
| `categories` | array of strings | Auto-assigned category tags |
| `immutable` | boolean | If true, prevents modification |
| `expiration_date` | datetime (nullable) | Auto-expiry date |
| `hash` | string | Content hash |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last modification timestamp |

Search results additionally include `score` (relevance metric).

## Processing Model

- Memories are processed **asynchronously by default** (`async_mode=true`)
- Add responses return queued events (`ADD`, `UPDATE`, `DELETE`) for tracking
- Set `async_mode=false` for synchronous processing when needed
- Graph metadata is processed asynchronously -- use `get_all()` for complete graph data

## Scoping Identifiers

Memories can be scoped to different levels:

| Scope | Parameter | Use Case |
|-------|-----------|----------|
| User | `user_id` | Per-user memory isolation |
| Agent | `agent_id` | Per-agent memory partitioning |
| Application | `app_id` | Cross-agent app-level memory |
| Run/Session | `run_id` | Session-scoped temporary memory |
| Organization | `org_id` | Org-level access control |
| Project | `project_id` | Project-level partitioning |

**Critical note:** Combining `user_id` and `agent_id` in a single AND filter yields empty results. Entities are stored separately. Use `OR` logic or separate queries.
