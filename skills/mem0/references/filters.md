# V2 Filter System -- Mem0 Platform

Comprehensive reference for the V2 memory filter system used in search and get-all operations.

## Table of Contents
- [Filter Architecture](#filter-architecture)
- [Logical Operators](#logical-operators)
- [Entity Fields](#entity-fields)
- [Temporal Fields](#temporal-fields)
- [Content Fields](#content-fields)
- [Comparison Operators](#comparison-operators)
- [Examples](#examples)
- [Critical Constraints](#critical-constraints)

## Filter Architecture

Filters use nested JSON with a logical operator at the root level:

```python
{
    "AND": [
        {"field": "value"},                    # Simple equality
        {"field": {"operator": "value"}}       # Operator-based comparison
    ]
}
```

The root **must** be `AND`, `OR`, or `NOT` with an array of conditions (for V2 structured filters). Simple shorthand `{"user_id": "alice"}` also works for basic cases.

## Logical Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `AND` | All conditions must match | `{"AND": [cond1, cond2]}` |
| `OR` | Any condition can match | `{"OR": [cond1, cond2]}` |
| `NOT` | Negation (nested inside AND/OR) | `{"AND": [{"NOT": {...}}]}` |

## Entity Fields

| Field | Valid Operators | Example |
|-------|-----------------|---------|
| `user_id` | `eq`, `ne`, `in`, `*` (wildcard) | `{"user_id": "user_123"}` |
| `agent_id` | `eq`, `ne`, `in`, `*` | `{"agent_id": "*"}` |
| `app_id` | `eq`, `ne`, `in`, `*` | `{"app_id": {"in": ["app1", "app2"]}}` |
| `run_id` | `eq`, `ne`, `in`, `*` | `{"run_id": "*"}` |

## Temporal Fields

| Field | Operators | Example |
|-------|-----------|---------|
| `created_at` | `gt`, `gte`, `lt`, `lte`, `eq`, `ne` | `{"created_at": {"gte": "2024-01-01"}}` |
| `updated_at` | `gt`, `gte`, `lt`, `lte`, `eq`, `ne` | `{"updated_at": {"lt": "2024-12-31"}}` |
| `timestamp` | `gt`, `gte`, `lt`, `lte`, `eq`, `ne` | `{"timestamp": {"gt": "2024-01-01"}}` |

Date format: ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`) or date-only (`YYYY-MM-DD`).

## Content Fields

| Field | Operators | Example |
|-------|-----------|---------|
| `categories` | `eq`, `ne`, `in`, `contains` | `{"categories": {"in": ["finance"]}}` |
| `metadata` | `eq`, `ne`, `contains` | `{"metadata": {"key": "value"}}` |
| `keywords` | `contains`, `icontains` | `{"keywords": {"icontains": "invoice"}}` |
| `memory_ids` | `in` | `{"memory_ids": ["id1", "id2"]}` |

## Comparison Operators

| Operator | Description |
|----------|-------------|
| `eq` | Equal to (default when plain value provided) |
| `ne` | Not equal to |
| `in` | Matches any of specified values (array) |
| `gt` | Greater than |
| `gte` | Greater than or equal to |
| `lt` | Less than |
| `lte` | Less than or equal to |
| `contains` | Case-sensitive containment |
| `icontains` | Case-insensitive containment |
| `*` | Wildcard -- matches any non-null value |

## Examples

### Single user
```python
filters = {"AND": [{"user_id": "user_123"}]}
```

### Multiple users
```python
filters = {"AND": [{"user_id": {"in": ["user_1", "user_2", "user_3"]}}]}
```

### Date range (January 2024)
```python
filters = {
    "AND": [
        {"user_id": "user_123"},
        {"created_at": {"gte": "2024-01-01T00:00:00Z"}},
        {"created_at": {"lt": "2024-02-01T00:00:00Z"}}
    ]
}
```

### OR logic
```python
filters = {
    "OR": [
        {"user_id": "user_123"},
        {"run_id": "run_456"}
    ]
}
```

### Exclude categories with NOT
```python
filters = {
    "AND": [
        {"user_id": "user_123"},
        {"NOT": {"categories": {"in": ["spam", "test"]}}}
    ]
}
```

### Category partial match
```python
filters = {
    "AND": [
        {"user_id": "alice"},
        {"categories": {"contains": "finance"}}
    ]
}
```

### Category exact match
```python
filters = {
    "AND": [
        {"user_id": "alice"},
        {"categories": {"in": ["personal_information"]}}
    ]
}
```

### Case-insensitive keyword search
```python
filters = {
    "AND": [
        {"user_id": "user_123"},
        {"keywords": {"icontains": "pizza"}}
    ]
}
```

### Wildcard (any non-null run)
```python
filters = {
    "AND": [
        {"user_id": "alice"},
        {"run_id": "*"}
    ]
}
```

### Multi-dimensional query
```python
filters = {
    "AND": [
        {"user_id": "user_123"},
        {"keywords": {"icontains": "invoice"}},
        {"categories": {"in": ["finance"]}},
        {"created_at": {"gte": "2024-01-01T00:00:00Z"}},
        {"created_at": {"lt": "2024-04-01T00:00:00Z"}}
    ]
}
```

## Critical Constraints

1. **Entity scope partitioning:** Combining `user_id` AND `agent_id` in one `AND` block yields **empty results**. Entities are stored separately. Use `OR` logic or separate queries.

2. **Metadata limitations:** Only supports top-level keys. Nested structures unsupported. Only `eq`, `contains`, and `ne` are valid for metadata. Operators like `in` or `gt` trigger validation errors.

3. **Operator syntax:** Must use exact keyword syntax (`gte`, `lt`, `ne`, etc.). SQL-style symbols (`>=`, `!=`, `<>`) are rejected.

4. **Entity filter required for get-all:** The `get_all` endpoint requires at least one of `app_id`, `user_id`, `agent_id`, or `run_id` in filters.

5. **Wildcard excludes null:** The `*` wildcard matches only non-null values. Null entries are excluded from results.

6. **Date format:** Use ISO 8601 format. Timezone-naive strings default to UTC.
