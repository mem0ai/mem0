# Search Memory -- Mem0 Platform

## Table of Contents
- [Endpoint](#endpoint)
- [Request Parameters](#request-parameters)
- [Filter System Overview](#filter-system-overview)
- [Common Filter Patterns](#common-filter-patterns)
- [SDK Usage](#sdk-usage)
- [Response Format](#response-format)
- [Common Pitfalls](#common-pitfalls)

## Endpoint

- **Method:** `POST`
- **URL:** `https://api.mem0.ai/v2/memories/search/`
- **Auth:** `Authorization: Token <MEM0_API_KEY>`

## Request Parameters

### Required

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Natural language search query |
| `filters` | object | Filter criteria (see [filters.md](filters.md) for complete reference) |

### Optional

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `top_k` | integer | `10` | Number of results to return |
| `rerank` | boolean | `false` | Enable result reranking for better relevance |
| `keyword_search` | boolean | `false` | Use keyword-based search instead of semantic |
| `filter_memories` | boolean | `false` | Additional memory filtering |
| `threshold` | number | `0.3` | Minimum similarity score threshold |
| `fields` | array of strings | -- | Specific fields to include in response |
| `version` | string | `v2` | Memory version |
| `enable_graph` | boolean | -- | Include graph relations in results |
| `org_id` | string | -- | Organization scope |
| `project_id` | string | -- | Project scope |

## Filter System Overview

Filters use a nested JSON structure with logical operators. The complete filter reference is in [filters.md](filters.md).

**Basic structure:**
```python
filters = {
    "AND": [
        {"user_id": "alice"},
        {"field": {"operator": "value"}}
    ]
}
```

**Root must be `AND`, `OR`, or `NOT` with an array of conditions.**

### Key Points About Filters

1. **Simple user filter** -- most common case:
   ```python
   filters={"user_id": "alice"}
   # SDK shorthand also works:
   client.search("query", user_id="alice")
   ```

2. **V2 structured filters** -- for complex queries:
   ```python
   filters={"AND": [{"user_id": "alice"}, {"categories": {"contains": "finance"}}]}
   ```

3. **Entity scope confusion** -- combining `user_id` AND `agent_id` in one AND block yields **empty results**. Use `OR` instead:
   ```python
   # WRONG: returns empty
   filters={"AND": [{"user_id": "alice"}, {"agent_id": "bot-1"}]}

   # CORRECT: use OR
   filters={"OR": [{"user_id": "alice"}, {"agent_id": "bot-1"}]}
   ```

## Common Filter Patterns

**Single user:**
```python
client.search("dietary preferences?", user_id="alice")
```

**OR across agents:**
```python
client.search(
    query="What are Alice's hobbies?",
    filters={
        "OR": [
            {"user_id": "alice"},
            {"agent_id": {"in": ["travel-agent", "sports-agent"]}}
        ]
    }
)
```

**Category filtering (partial match):**
```python
client.search(
    query="financial goals?",
    filters={
        "AND": [
            {"user_id": "alice"},
            {"categories": {"contains": "finance"}}
        ]
    }
)
```

**Category filtering (exact match):**
```python
client.search(
    query="personal info?",
    filters={
        "AND": [
            {"user_id": "alice"},
            {"categories": {"in": ["personal_information"]}}
        ]
    }
)
```

**Wildcard (match any non-null run):**
```python
client.search(
    query="hobbies?",
    filters={
        "AND": [
            {"user_id": "alice"},
            {"run_id": "*"}
        ]
    }
)
```

**Date range:**
```python
client.search(
    query="recent updates",
    filters={
        "AND": [
            {"user_id": "alice"},
            {"created_at": {"gte": "2024-01-01T00:00:00Z"}},
            {"created_at": {"lt": "2024-02-01T00:00:00Z"}}
        ]
    }
)
```

## SDK Usage

**Python:**
```python
results = client.search("What are my dietary restrictions?", user_id="user123")
```

**Python with advanced filters:**
```python
results = client.search(
    query="What are my dietary restrictions?",
    filters={"AND": [{"user_id": "user123"}]},
    top_k=5,
    rerank=True,
    threshold=0.5
)
```

**JavaScript:**
```javascript
const results = await client.search("What are my dietary restrictions?", {
    user_id: "user123"
});
```

**cURL:**
```bash
curl -X POST https://api.mem0.ai/v2/memories/search/ \
  -H "Authorization: Token $MEM0_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "dietary restrictions", "filters": {"user_id": "user123"}}'
```

## Response Format

```json
{
  "results": [
    {
      "id": "ea925981-272f-40dd-b576-be64e4871429",
      "memory": "Is a vegetarian and allergic to nuts.",
      "user_id": "user123",
      "metadata": {"source": "onboarding_form"},
      "categories": ["food", "health"],
      "score": 0.89,
      "created_at": "2024-07-26T10:29:36.630547-07:00",
      "updated_at": null,
      "immutable": false,
      "expiration_date": null
    }
  ]
}
```

When `enable_graph=True`, response includes additional `relations` array:
```json
{
  "results": [...],
  "relations": [
    {
      "source": "Alice",
      "source_type": "Person",
      "relationship": "allergic_to",
      "target": "Nuts",
      "target_type": "Food",
      "score": 0.85
    }
  ]
}
```

**Graph relations:**
```python
results = client.search("what is my name?", user_id="joseph", enable_graph=True)
# Response includes "relations" array with entity relationships
```

**Keyword search:**
```python
results = client.search("vegetarian", user_id="user123", keyword_search=True)
```

## Common Pitfalls

1. **Entity cross-filtering fails silently** -- `AND` with `user_id` + `agent_id` returns empty. Use `OR`.
2. **SQL operators rejected** -- use `gte`, `lt`, etc. Not `>=`, `<`.
3. **Metadata filtering is limited** -- only supports top-level keys with `eq`, `contains`, `ne`. No `in` or `gt` for metadata.
4. **Wildcard `*` excludes null** -- only matches non-null values.
5. **Default threshold is 0.3** -- low-confidence results may appear. Increase `threshold` for stricter matching.

To search memories via CLI, run: `python scripts/search_memory.py --help`
For complete filter reference, see [filters.md](filters.md).
