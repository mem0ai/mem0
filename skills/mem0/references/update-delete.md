# Update, Delete & Get Memory -- Mem0 Platform

## Table of Contents
- [Get Single Memory](#get-single-memory)
- [Get All Memories](#get-all-memories)
- [Update Memory](#update-memory)
- [Delete Memory](#delete-memory)
- [Delete All Memories](#delete-all-memories)
- [Memory History](#memory-history)

## Get Single Memory

### Endpoint
- **Method:** `GET`
- **URL:** `https://api.mem0.ai/v1/memories/{memory_id}/`

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `memory_id` | string (UUID) | Yes | Path parameter: unique memory identifier |

### SDK Usage

**Python:**
```python
memory = client.get(memory_id="ea925981-272f-40dd-b576-be64e4871429")
```

**JavaScript:**
```javascript
const memory = await client.get("ea925981-272f-40dd-b576-be64e4871429");
```

### Response (200)
Returns full memory object: `id`, `memory`, `user_id`, `agent_id`, `app_id`, `run_id`, `hash`, `metadata`, `created_at`, `updated_at`.

### Error (404)
```json
{"error": "Memory not found!"}
```

---

## Get All Memories

### Endpoint
- **Method:** `POST`
- **URL:** `https://api.mem0.ai/v2/memories/`

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filters` | object | Yes | Filter dictionary (at least one entity filter required) |
| `fields` | array of strings | No | Specific fields to include |
| `page` | integer | No | Page number (default: 1) |
| `page_size` | integer | No | Items per page (default: 100) |

**Critical:** At least one of `user_id`, `agent_id`, `app_id`, or `run_id` must be in filters.

### SDK Usage

**Python:**
```python
memories = client.get_all(filters={"AND": [{"user_id": "alice"}]})
```

**Python with date range:**
```python
memories = client.get_all(
    filters={
        "AND": [
            {"user_id": "alex"},
            {"created_at": {"gte": "2024-07-01", "lte": "2024-07-31"}}
        ]
    }
)
```

**Python with graph:**
```python
memories = client.get_all(
    filters={"AND": [{"user_id": "alice"}]},
    enable_graph=True
)
```

**JavaScript:**
```javascript
const memories = await client.getAll({
    filters: {"AND": [{"user_id": "alice"}]}
});
```

### Response
Returns array of memory objects plus `total_memories` count. With `enable_graph=True`, includes a top-level `relations` array and each memory may contain an `entities` array.

### Error (400)
```json
{"message": "One of the filters: app_id, user_id, agent_id, run_id is required!"}
```

---

## Update Memory

### Endpoint
- **Method:** `PUT`
- **URL:** `https://api.mem0.ai/v1/memories/{memory_id}/`
- **Content-Type:** `application/json`

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `memory_id` | string (UUID) | Yes | Path parameter: memory to update |
| `text` | string | No | New text content |
| `metadata` | object | No | Updated metadata key-value pairs |

### SDK Usage

**Python:**
```python
client.update(memory_id="ea925981-...", text="Updated dietary info: vegan since 2024")
```

**Python with metadata:**
```python
client.update(
    memory_id="ea925981-...",
    text="Updated text",
    metadata={"verified": True, "source": "user_correction"}
)
```

**JavaScript:**
```javascript
await client.update("ea925981-...", { text: "Updated dietary info: vegan since 2024" });
```

**cURL:**
```bash
curl -X PUT https://api.mem0.ai/v1/memories/ea925981-.../ \
  -H "Authorization: Token $MEM0_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Updated text", "metadata": {"verified": true}}'
```

### Response (200)
Returns updated memory object with all fields including new `updated_at` timestamp.

### Notes
- Cannot update immutable memories (those created with `immutable=true`)
- Updates change the `hash` field

---

## Delete Memory

### Endpoint
- **Method:** `DELETE`
- **URL:** `https://api.mem0.ai/v1/memories/{memory_id}/`

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `memory_id` | string (UUID) | Yes | Path parameter: memory to delete |

### SDK Usage

**Python:**
```python
client.delete(memory_id="ea925981-272f-40dd-b576-be64e4871429")
```

**JavaScript:**
```javascript
await client.delete("ea925981-272f-40dd-b576-be64e4871429");
```

**cURL:**
```bash
curl -X DELETE https://api.mem0.ai/v1/memories/ea925981-.../ \
  -H "Authorization: Token $MEM0_API_KEY"
```

### Response (204)
```json
{"message": "Memory deleted successfully!"}
```

---

## Delete All Memories

Bulk deletion by user scope.

### SDK Usage

**Python:**
```python
client.delete_all(user_id="alice")
```

**JavaScript:**
```javascript
await client.deleteAll({ user_id: "alice" });
```

### Notes
- No dedicated REST endpoint for bulk delete; the SDK handles iteration internally
- Use with caution -- this is irreversible
- Can scope by `user_id`, `agent_id`, `app_id`, or `run_id`

---

## Memory History

Track changes to a specific memory over time.

### SDK Usage

**Python:**
```python
history = client.history(memory_id="ea925981-...")
```

**JavaScript:**
```javascript
const history = await client.history("ea925981-...");
```

### Response
Returns array of history entries with `previous_value`, `new_value`, `action`, and timestamps.

CLI tools for these operations:
- `python scripts/update_memory.py --help`
- `python scripts/delete_memory.py --help`
- `python scripts/get_memories.py --help`
