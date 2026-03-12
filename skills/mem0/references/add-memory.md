# Add Memory -- Mem0 Platform

## Table of Contents
- [Endpoint](#endpoint)
- [Vector vs Graph Memory](#vector-vs-graph-memory)
- [Request Parameters](#request-parameters)
- [SDK Usage](#sdk-usage)
- [Response Format](#response-format)
- [Advanced Options](#advanced-options)

## Endpoint

- **Method:** `POST`
- **URL:** `https://api.mem0.ai/v1/memories/`
- **Content-Type:** `application/json`
- **Auth:** `Authorization: Token <MEM0_API_KEY>`

## Vector vs Graph Memory

Mem0 supports two memory storage modes:

### Vector Memory (Default)
- Stores memories as embeddings in vector space
- Semantic similarity search
- Available on all plans
- Default behavior when `enable_graph` is not set

### Graph Memory (Pro Plan Required)
- Creates entity nodes and relationships in a knowledge graph
- Enables multi-hop relationship traversal
- Adds a `relations` array to search results containing source/target entity pairs
- **Requires Pro plan** -- not available on free tier
- Activated by setting `enable_graph=true` per request or at project level
- Graph metadata is processed asynchronously; use `get_all()` for complete graph data
- Graph relations augment vector results **without reordering them**

**Enable per request:**
```python
client.add(messages, user_id="alice", enable_graph=True)
```

**Enable at project level (applies to all subsequent operations):**
```python
client.project.update(enable_graph=True)
```

See [graph-memory.md](graph-memory.md) for complete graph memory details.

## Request Parameters

### Core Fields

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `messages` | array | Yes | Conversation turns: `[{"role": "user", "content": "..."}]` |
| `user_id` | string | Recommended | Scopes memory to a specific user |
| `metadata` | object | Optional | Custom key-value pairs for context |

### Processing Controls

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `infer` | boolean | `true` | When `false`, stores text as-is without inference |
| `async_mode` | boolean | `true` | Asynchronous processing; `false` for synchronous |
| `output_format` | string | `v1.1` | Response structure format |
| `version` | string | -- | Memory version; `v2` recommended (`v1` deprecated) |

### Scoping

| Parameter | Type | Description |
|-----------|------|-------------|
| `agent_id` | string | Agent identifier |
| `app_id` | string | Application identifier |
| `run_id` | string | Run/session identifier |
| `project_id` | string | Project identifier |
| `org_id` | string | Organization identifier |

### Advanced Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_graph` | boolean | -- | Activate knowledge graph (Pro plan) |
| `custom_categories` | object | -- | Category definitions with descriptions |
| `custom_instructions` | string | -- | Project-specific memory extraction guidelines |
| `immutable` | boolean | `false` | Prevents modification after creation |
| `timestamp` | integer | -- | Unix timestamp format |
| `expiration_date` | string | -- | Format: `YYYY-MM-DD` |
| `includes` | string | -- | Preference filters for inclusion (min length: 1) |
| `excludes` | string | -- | Preference filters for exclusion (min length: 1) |

## SDK Usage

**Python:**
```python
messages = [
    {"role": "user", "content": "I'm a vegetarian and allergic to nuts."},
    {"role": "assistant", "content": "Got it! I'll remember your dietary preferences."}
]
client.add(messages, user_id="user123")
```

**Python with metadata:**
```python
client.add(messages, user_id="user123", metadata={"source": "onboarding_form"})
```

**Python with graph:**
```python
client.add(messages, user_id="user123", enable_graph=True)
```

**JavaScript:**
```javascript
await client.add(messages, { user_id: "user123" });
```

**JavaScript with graph:**
```javascript
await client.add({ messages, user_id: "user123", enable_graph: true });
```

**cURL:**
```bash
curl -X POST https://api.mem0.ai/v1/memories/ \
  -H "Authorization: Token $MEM0_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I moved to Austin last month."}
    ],
    "user_id": "alice",
    "metadata": {"source": "onboarding_form"}
  }'
```

## Response Format

**Success (200):**
```json
[
  {
    "id": "mem_01JF8ZS4Y0R0SPM13R5R6H32CJ",
    "event": "ADD",
    "data": {
      "memory": "The user moved to Austin in 2025."
    }
  }
]
```

Event types: `ADD`, `UPDATE`, `DELETE`. A single add operation can trigger multiple events (e.g., updating an existing memory and adding a new one).

**Error (400):**
```json
{
  "error": "400 Bad Request",
  "details": {
    "message": "Invalid input data. Please refer to the memory creation documentation..."
  }
}
```

## Advanced Options

### Immutable Memories
```python
client.add(messages, user_id="alice", immutable=True)
```
Once set, the memory cannot be modified or overwritten.

### Expiring Memories
```python
client.add(messages, user_id="alice", expiration_date="2025-12-31")
```

### Selective Extraction
```python
client.add(messages, user_id="alice", includes="dietary preferences", excludes="payment info")
```

### Agent and Session Scoping
```python
client.add(messages, user_id="alice", agent_id="nutrition-agent", run_id="session-456")
```

### Synchronous Processing
```python
# Wait for processing to complete before returning
client.add(messages, user_id="alice", async_mode=False)
```

### Raw Text (Skip Inference)
```python
# Store text as-is without LLM extraction
client.add(
    [{"role": "user", "content": "User prefers dark mode."}],
    user_id="alice",
    infer=False,
)
```

To add memories via CLI, run: `python scripts/add_memory.py --help`
