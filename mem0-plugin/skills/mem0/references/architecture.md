# Mem0 Platform Architecture

How Mem0 processes, stores, and retrieves memories under the hood.

## Table of Contents

- [Core Concept](#core-concept)
- [Memory Processing Pipeline](#memory-processing-pipeline)
- [Retrieval Pipeline](#retrieval-pipeline)
- [Memory Lifecycle](#memory-lifecycle)
- [Memory Object Structure](#memory-object-structure)
- [Scoping & Multi-Tenancy](#scoping--multi-tenancy)
- [Memory Layers](#memory-layers)
- [Performance Characteristics](#performance-characteristics)

---

## Core Concept

Mem0 is a managed memory layer that sits between your AI application and users. Every integration follows the same 3-step loop:

```
User Input → Retrieve relevant memories → Enrich LLM prompt → Generate response → Store new memories
```

Mem0 handles the complexity of extraction, deduplication, conflict resolution, and semantic retrieval so your application only needs to call `search()` and `add()`.

**Dual storage architecture:**
- **Vector store**: Embeddings for semantic similarity search
- **Graph store** (optional): Entity nodes and relationship edges for structured knowledge

---

## Memory Processing Pipeline

### What happens when you call `client.add()`

```
Messages In
    │
    ▼
┌─────────────────────┐
│  1. EXTRACTION       │  LLM analyzes messages, extracts key facts
│     (infer=True)     │  If infer=False, stores raw text as-is
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  2. CONFLICT         │  Checks existing memories for duplicates
│     RESOLUTION       │  Latest truth wins (newer overrides older)
│                      │  Only runs when infer=True
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  3. STORAGE          │  Generates embeddings → vector store
│                      │  Optional: entity extraction → graph store
│                      │  Indexes metadata, categories, timestamps
└─────────┬───────────┘
          │
          ▼
    Memory Object
    (id, memory, categories, structured_attributes)
```

### Processing modes

**Async (default, `async_mode=True`):**
- API returns immediately: `{"status": "PENDING", "event_id": "..."}`
- Processing happens in background
- Use webhooks for completion notifications
- Best for: high-throughput, non-blocking workflows

**Sync (`async_mode=False`):**
- API waits for full processing
- Returns complete memory object with `id`, `event`, `memory`
- Best for: real-time access immediately after add

### Extraction modes

**Inferred (`infer=True`, default):**
- LLM extracts structured facts from conversation
- Conflict resolution deduplicates and resolves contradictions
- Best for: natural conversation → memory

**Raw (`infer=False`):**
- Stores text exactly as provided, no LLM processing
- Skips conflict resolution — same fact can be stored twice
- Only `user` role messages are stored; `assistant` messages ignored
- Best for: bulk imports, pre-structured data, migrations

**Warning:** Don't mix `infer=True` and `infer=False` for the same data — the same fact will be stored twice.

---

## Retrieval Pipeline

### What happens when you call `client.search()`

```
Query In
    │
    ▼
┌─────────────────────┐
│  1. QUERY EMBEDDING  │  Convert query to vector representation
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  2. VECTOR SEARCH    │  Cosine similarity across stored embeddings
│                      │  Scoped by filters (user_id, agent_id, etc.)
└─────────┬───────────┘
          │
          ▼  (optional enhancements)
┌─────────────────────┐
│  3a. KEYWORD SEARCH  │  Expands results with specific terms (+10ms)
│  3b. RERANKING       │  Deep semantic reordering (+150-200ms)
│  3c. FILTER MEMORIES │  Precision filtering, removes low-relevance (+200-300ms)
└─────────┬───────────┘
          │
          ▼  (if enable_graph=True)
┌─────────────────────┐
│  4. GRAPH LOOKUP     │  Finds entity relationships
│                      │  Appends relations WITHOUT reranking vector results
└─────────┬───────────┘
          │
          ▼
    Results + Relations
```

### Retrieval enhancement combinations

| Configuration | Latency | Best for |
|--------------|---------|----------|
| Base search only | ~100ms | Simple lookups |
| `keyword_search=True` | ~110ms | Entity-heavy queries, broad coverage |
| `rerank=True` | ~250-300ms | User-facing results, top-N precision |
| `keyword_search=True` + `rerank=True` | ~310ms | Balanced (recommended for most apps) |
| `rerank=True` + `filter_memories=True` | ~400-500ms | Safety-critical, production systems |

### Implicit null scoping

When you search with `user_id="alice"` only, Mem0 returns memories where `agent_id`, `app_id`, and `run_id` are all null. This prevents cross-scope leakage by default.

To include memories with non-null fields, use explicit filters:
```python
# Gets memories for alice regardless of agent/app/run
filters={"OR": [{"user_id": "alice"}]}
```

---

## Memory Lifecycle

```
CREATE ──→ ACTIVE ──→ UPDATE ──→ ACTIVE
  │           │                     │
  │           ▼                     ▼
  │       EXPIRED              EXPIRED
  │      (still stored,       (still stored,
  │       not retrieved)       not retrieved)
  │           │                     │
  ▼           ▼                     ▼
DELETE    DELETE               DELETE
(permanent)
```

### Creation
- Triggered by `client.add(messages, user_id="...")`
- Messages processed through extraction → conflict resolution → storage
- Gets unique UUID, `created_at` timestamp
- Optional: custom `timestamp`, `expiration_date`, `metadata`, `immutable`

### Updates
- `client.update(memory_id, text="...")` replaces text and reindexes
- `client.batch_update([...])` for up to 1000 memories at once
- Immutable memories (`immutable=True`) cannot be updated — must delete and re-add

### Deduplication
- Automatic during `add()` with `infer=True`
- Conflict resolution merges duplicate facts
- Latest truth wins when contradictions detected
- Prevents memory bloat from repeated information

### Expiration
- Optional `expiration_date` parameter (ISO 8601 or `YYYY-MM-DD`)
- After expiration: memory NOT returned in searches but remains in storage
- Useful for time-sensitive info (events, temporary preferences, session state)

### Deletion
- Single: `client.delete(memory_id)` — permanent, no recovery
- Batch: `client.batch_delete([memory_ids])` — up to 1000
- Bulk: `client.delete_all(user_id="alice")` — all memories for entity
- `delete_all()` without filters raises error to prevent accidental data loss

### History tracking
- `client.history(memory_id)` returns version timeline
- Shows all changes: `{previous_value, new_value, action, timestamps}`
- Useful for audit trails and debugging

---

## Memory Object Structure

```json
{
  "id": "uuid-string",
  "memory": "Extracted memory text",
  "user_id": "user-identifier",
  "agent_id": null,
  "app_id": null,
  "run_id": null,
  "metadata": { "source": "chat", "priority": "high" },
  "categories": ["health", "preferences"],
  "created_at": "2025-03-12T12:34:56Z",
  "updated_at": "2025-03-12T12:34:56Z",
  "expiration_date": null,
  "immutable": false,
  "structured_attributes": {
    "day": 12, "month": 3, "year": 2025,
    "hour": 12, "minute": 34,
    "day_of_week": "wednesday",
    "is_weekend": false,
    "quarter": 1, "week_of_year": 11
  },
  "score": 0.85
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique identifier, used for update/delete |
| `memory` | string | Extracted or stored text content |
| `user_id` | string | Primary entity scope |
| `agent_id` | string | Agent scope |
| `app_id` | string | Application scope |
| `run_id` | string | Session/run scope |
| `metadata` | object | Custom key-value pairs for filtering |
| `categories` | array | Auto-assigned or custom category tags |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last modification timestamp |
| `expiration_date` | datetime | Auto-expiry date (stops retrieval, data persists) |
| `immutable` | boolean | If true, prevents modification |
| `structured_attributes` | object | Temporal breakdown for time-based queries |
| `score` | float | Semantic similarity (search results only, 0-1) |

---

## Scoping & Multi-Tenancy

Mem0 separates memories across four dimensions to prevent data mixing:

| Dimension | Field | Purpose | Example |
|-----------|-------|---------|---------|
| User | `user_id` | Persistent persona or account | `"customer_6412"` |
| Agent | `agent_id` | Distinct agent or tool | `"meal_planner"` |
| App | `app_id` | Product surface or deployment | `"ios_retail_app"` |
| Session | `run_id` | Short-lived flow or thread | `"ticket-9241"` |

### Storage model

Each entity combination creates separate records. A memory with `user_id="alice"` is stored separately from one with `user_id="alice"` + `agent_id="bot"`.

### Critical: cross-entity queries

```python
# This returns NOTHING — user and agent memories are stored separately
filters={"AND": [{"user_id": "alice"}, {"agent_id": "bot"}]}

# Use OR to query multiple scopes
filters={"OR": [{"user_id": "alice"}, {"agent_id": "bot"}]}

# Use wildcard to include any non-null value
filters={"AND": [{"user_id": "*"}]}  # All users (excludes null)
```

### Recommended scoping patterns

```python
# User-level: persistent preferences
client.add(messages, user_id="alice")

# Session-level: temporary context
client.add(messages, user_id="alice", run_id="session_123")
# Clean up when done: client.delete_all(run_id="session_123")

# Agent-level: agent-specific knowledge
client.add(messages, agent_id="support_bot", app_id="helpdesk")

# Multi-tenant: full isolation
client.add(messages, user_id="alice", agent_id="bot", app_id="acme_corp", run_id="ticket_42")
```

---

## Memory Layers

Mem0 supports three layers of memory, from shortest to longest lived:

### Conversation memory
- In-flight messages within a single turn
- Tool calls, chain-of-thought reasoning
- **Lifetime:** Single response — lost after turn finishes
- **Managed by:** Your application, not Mem0

### Session memory
- Short-lived facts for current task or channel
- Multi-step flows (onboarding, debugging, support tickets)
- **Lifetime:** Minutes to hours
- **Managed by:** Mem0 via `run_id` parameter
- Clean up with `client.delete_all(run_id="session_id")`

### User memory
- Long-lived knowledge tied to a person or account
- Personal preferences, account state, compliance details
- **Lifetime:** Weeks to forever
- **Managed by:** Mem0 via `user_id` parameter
- Persists across all sessions and interactions

### How layering works in practice

```python
def chat(user_input: str, user_id: str, session_id: str) -> str:
    # 1. Retrieve user memories (long-term preferences)
    user_mems = mem0.search(user_input, user_id=user_id)

    # 2. Retrieve session memories (current task context)
    session_mems = mem0.search(user_input, filters={
        "AND": [{"user_id": user_id}, {"run_id": session_id}]
    })

    # 3. Combine both layers for LLM context
    context = format_memories(user_mems) + format_memories(session_mems)

    # 4. Generate response
    response = llm.generate(context=context, input=user_input)

    # 5. Store in session scope (temporary) + user scope (persistent)
    messages = [{"role": "user", "content": user_input}, {"role": "assistant", "content": response}]
    mem0.add(messages, user_id=user_id, run_id=session_id)

    return response
```

---

## Performance Characteristics

### Latency

| Operation | Typical Latency |
|-----------|----------------|
| Base vector search | ~100ms |
| + keyword_search | +10ms |
| + reranking | +150-200ms |
| + filter_memories | +200-300ms |
| Add (async, default) | < 50ms response, background processing |
| Add (sync) | 500ms-2s depending on extraction complexity |
| Graph operations | Slight overhead for large stores |

### Processing

- **Async mode (default):** Returns immediately, processes in background
- **Sync mode:** Waits for full extraction + storage pipeline
- **Batch operations:** Up to 1000 memories per batch_update/batch_delete
- **Webhooks:** Real-time notifications when async processing completes

### Scoping strategy for performance

- Use `user_id` for all user-facing queries (most common, fastest)
- Add `run_id` for session isolation (narrows search space)
- Avoid wildcard `"*"` filters on large datasets (scans all non-null records)
- Use `top_k` to limit result count when you only need a few memories

---

## Comparison with Alternatives

| Approach | Pros | Cons |
|----------|------|------|
| **Raw vector DB** | Fast, full control | No extraction, no dedup, no conflict resolution |
| **In-memory chat history** | Zero latency | Lost on restart, no cross-session, grows unbounded |
| **RAG over documents** | Good for static knowledge | No personalization, no memory updates |
| **Mem0 Platform** | Managed extraction + dedup + graph + scoping | External dependency, async processing delay |

Mem0 combines the best of vector search (semantic retrieval) with automatic extraction (LLM-powered), conflict resolution (deduplication), and structured scoping (multi-tenancy) — in a single managed API.
