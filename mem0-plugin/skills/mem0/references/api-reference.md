# Mem0 Platform API Reference

REST API endpoints for the Mem0 Platform. Base URL: `https://api.mem0.ai`

All endpoints require: `Authorization: Token <MEM0_API_KEY>`

## Endpoints

| Operation | Method | URL |
|-----------|--------|-----|
| Add Memories | `POST` | `/v1/memories/` |
| Search Memories | `POST` | `/v2/memories/search/` |
| Get All Memories | `POST` | `/v2/memories/` |
| Get Single Memory | `GET` | `/v1/memories/{memory_id}/` |
| Update Memory | `PUT` | `/v1/memories/{memory_id}/` |
| Delete Memory | `DELETE` | `/v1/memories/{memory_id}/` |

## Memory Object Structure

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

## Scoping Identifiers

Memories can be scoped to different levels:

| Scope | Parameter | Use Case |
|-------|-----------|----------|
| User | `user_id` | Per-user memory isolation |
| Agent | `agent_id` | Per-agent memory partitioning |
| Application | `app_id` | Cross-agent app-level memory |
| Run/Session | `run_id` | Session-scoped temporary memory |

**Critical:** Combining `user_id` and `agent_id` in a single AND filter yields empty results. Entities are stored separately. Use `OR` logic or separate queries.

## Processing Model

- Memories are processed **asynchronously by default** (`async_mode=true`)
- Add responses return queued events (`ADD`, `UPDATE`, `DELETE`) for tracking
- Set `async_mode=false` for synchronous processing when needed
- Graph metadata is processed asynchronously -- use `get_all()` for complete graph data

## Filter System

Filters use nested JSON with a logical operator at the root:

```json
{
    "AND": [
        {"user_id": "alice"},
        {"categories": {"contains": "finance"}},
        {"created_at": {"gte": "2024-01-01"}}
    ]
}
```

Root must be `AND`, `OR`, or `NOT`. Simple shorthand `{"user_id": "alice"}` also works.

### Supported Operators

| Operator | Description |
|----------|-------------|
| `eq` | Equal to (default) |
| `ne` | Not equal to |
| `in` | Matches any value in array |
| `gt`, `gte` | Greater than / greater than or equal |
| `lt`, `lte` | Less than / less than or equal |
| `contains` | Case-sensitive containment |
| `icontains` | Case-insensitive containment |
| `*` | Wildcard -- matches any non-null value |

### Filterable Fields

| Field | Valid Operators |
|-------|-----------------|
| `user_id`, `agent_id`, `app_id`, `run_id` | `eq`, `ne`, `in`, `*` |
| `created_at`, `updated_at`, `timestamp` | `gt`, `gte`, `lt`, `lte`, `eq`, `ne` |
| `categories` | `eq`, `ne`, `in`, `contains` |
| `metadata` | `eq`, `ne`, `contains` (top-level keys only) |
| `keywords` | `contains`, `icontains` |
| `memory_ids` | `in` |

### Filter Constraints

1. **Entity scope partitioning:** `user_id` AND `agent_id` in one `AND` block yields empty results.
2. **Metadata limitations:** Only top-level keys. Only `eq`, `contains`, `ne`. No `in` or `gt`.
3. **Operator syntax:** Use `gte`, `lt`, `ne`. SQL-style (`>=`, `!=`) rejected.
4. **Entity filter required for get-all:** At least one of `user_id`, `agent_id`, `app_id`, or `run_id`.
5. **Wildcard excludes null:** `*` matches only non-null values.
6. **Date format:** ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`). Timezone-naive defaults to UTC.

## Response Formats

### Add Response

```json
[
  {
    "id": "mem_01JF8ZS4Y0R0SPM13R5R6H32CJ",
    "event": "ADD",
    "data": { "memory": "The user moved to Austin in 2025." }
  }
]
```

Event types: `ADD`, `UPDATE`, `DELETE`. A single add can trigger multiple events.

### Search Response

```json
{
  "results": [
    {
      "id": "ea925981-...",
      "memory": "Is a vegetarian and allergic to nuts.",
      "user_id": "user123",
      "categories": ["food", "health"],
      "score": 0.89,
      "created_at": "2024-07-26T10:29:36.630547-07:00"
    }
  ]
}
```

With `enable_graph=true`, includes additional `relations` array with entity relationships.
