# Mem0 Platform API Reference

REST API endpoints for the Mem0 Platform. Base URL: `https://api.mem0.ai`

All endpoints require: `Authorization: Token <MEM0_API_KEY>`

## Endpoints

| Operation | Method | URL |
|-----------|--------|-----|
| Add Memories | `POST` | `/v3/memories/add/` |
| Search Memories | `POST` | `/v3/memories/search/` |
| Get All Memories | `POST` | `/v3/memories/` |
| Get Single Memory | `GET` | `/v1/memories/{memory_id}/` |
| Update Memory | `PUT` | `/v1/memories/{memory_id}/` |
| Delete Memory | `DELETE` | `/v1/memories/{memory_id}/` |
| Memory History | `GET` | `/v1/memories/{memory_id}/history/` |
| Delete by Filter | `DELETE` | `/v1/memories/` (query params `user_id`, `agent_id`, `app_id`, `run_id`, `metadata`; `*` matches all) |
| Batch Update / Delete | `PUT` / `DELETE` | `/v1/batch/` (max 1000 memories per request) |
| Feedback | `POST` | `/v1/feedback/` |
| Create / Get Export | `POST` | `/v1/exports/`, `/v1/exports/get/` |
| List Entities | `GET` | `/v1/entities/` |
| Delete Entity | `DELETE` | `/v2/entities/{entity_type}/{entity_id}/` |
| Event Status | `GET` | `/v1/event/{event_id}/` |

The `GET`/`POST` `/v1/memories/`, `POST` `/v2/memories/`, and `POST` `/v1/memories/search/` and `/v2/memories/search/` endpoints are marked deprecated in the OpenAPI spec. Use the `/v3/` endpoints above.

## Memory Object Structure

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (UUID) | Unique memory identifier |
| `memory` | string | Text content of the memory |
| `user_id` | string | Associated user |
| `agent_id` | string (nullable) | Agent identifier |
| `app_id` | string (nullable) | Application identifier |
| `run_id` | string (nullable) | Run/session identifier (see note below) |
| `metadata` | object | Custom key-value pairs |
| `categories` | array of strings | Auto-assigned category tags |
| `expiration_date` | string (nullable) | Date after which the memory is hidden unless `show_expired` is true |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last modification timestamp |

Search results additionally include `score` (relevance metric) and `score_breakdown` (per-signal scores). Get and get-all results additionally include `structured_attributes` (temporal breakdown of the creation time), `replaced_by`, and `synthesized`, and get also returns `lifecycle_state`. Get and get-all omit `app_id` and `run_id` when they are not set.

The run/session identifier is `run_id` in search results but `session_id` in get, get-all, and history results.

## Scoping Identifiers

Memories can be scoped to different levels:

| Scope | Parameter | Use Case |
|-------|-----------|----------|
| User | `user_id` | Per-user memory isolation |
| Agent | `agent_id` | Per-agent memory partitioning |
| Application | `app_id` | Cross-agent app-level memory |
| Run/Session | `run_id` | Session-scoped temporary memory |

**Critical:** Combining `user_id` and `agent_id` in a single AND filter yields empty results for memories created with `infer=true`. Each extracted fact is attributed to its speaker, so a record carries `user_id` (user messages) or `agent_id` (assistant messages), not both. Use `OR` logic or separate queries. Only Direct Import (`infer=false`) writes both fields on one record. `app_id` and `run_id` are stored on every record.

Filters only constrain the entities you mention. `{"user_id": "alice"}` does not require `agent_id`, `app_id`, or `run_id` to be null.

## Processing Model

- Memories are processed **asynchronously** (v3 default)
- Add responses return a `PENDING` event (v3 is ADD-only, no UPDATE/DELETE)
- Poll status via `GET /v1/event/{event_id}/` (`PENDING`, `RUNNING`, `FAILED`, `SUCCEEDED`)
- `infer=false` is synchronous: memories are stored verbatim and the response carries `message` and `results`

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

The root can also be a bare condition such as `{"user_id": "alice"}`. Sibling top-level keys in a flat object are implicitly ANDed. Use `AND`, `OR`, or `NOT` for OR/NOT semantics or nesting. An unrecognized top-level key returns a 400.

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
| `created_at`, `updated_at`, `timestamp`, `expiration_date` | `gt`, `gte`, `lt`, `lte`, `ne` (explicit `eq` is rejected, pass a bare value; `in` fails with a 503 in search and a 500 in get-all) |
| `categories` | `in`, `contains` (`eq` and `ne` are rejected) |
| `metadata` | `eq`, `ne`, `contains` (top-level keys only). `contains` is case-sensitive and matches the whole stored value or one member of a list value, not a substring. `icontains` is rejected with a 400 |
| `keywords` | `contains`, `icontains` |
| `memory_ids` | plain list of UUIDs (no `in`) |

### Filter Constraints

1. **Entity scope partitioning:** `user_id` AND `agent_id` in one `AND` block yields empty results (except for Direct Import records).
2. **Metadata limitations:** Only top-level keys. Only `eq`, `contains`, `ne`. No `in` or `gt`.
3. **Operator syntax:** Use `gte`, `lt`, `ne`. SQL-style (`>=`, `!=`) rejected. There is no `nin` on Platform: use `{"NOT": [{"categories": {"in": [...]}}]}`.
4. **Filters required for get-all:** Empty or missing `filters` return a 400. Scope the listing with at least one of `user_id`, `agent_id`, `app_id`, or `run_id` (search enforces this, get-all does not).
5. **Wildcard excludes null:** `*` matches only non-null values.
6. **Date format:** ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`). Timezone-naive defaults to UTC.
7. **Keyword filter:** `keywords` works in `get_all` filters but returns a 503 inside `search()` filters (MEM-5746). Pass the text as `query` for search.

## Response Formats

### Add Response (v3)

```json
{
  "event_id": "evt-uuid",
  "status": "PENDING"
}
```

v3 is ADD-only. No UPDATE or DELETE events. With `infer=false` the call is synchronous and the response also carries `message` and `results` (`[{"id": ..., "data": {"memory": ...}, "event": "ADD"}]`).

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

In v3, `score` is a combined multi-signal relevance score in [0, 1]. Request defaults: `top_k` 10 (1 to 1000), `rerank` false. `threshold` is a server-side cutoff applied before score blending, not a floor on the returned `score`: the default and `0.0` returned the same or nearly the same results in live tests, including scores below 0.1.

### Get All Response (v3)

```json
{
  "count": 123,
  "next": "https://api.mem0.ai/v3/memories/?page=2&page_size=50",
  "previous": null,
  "results": [...]
}
```

v3 returns paginated envelope. Use `page` (default 1) and `page_size` (default 100, max 200) query params.
