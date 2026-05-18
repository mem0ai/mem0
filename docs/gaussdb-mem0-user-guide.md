# Mem0 GaussDB User Guide

> Updated: 2026-05-18  
> Audience: application developers, DBAs, QA, solution teams, support engineers

## 1. What this guide is for

This guide explains how to use the GaussDB vector store provider in real Mem0 deployments.

It focuses on:

- how to configure the provider
- what centralized and distributed modes support
- how scoped filtering works
- how metadata filters behave
- what to expect from range filters, wildcard, `exists`, `missing`, and `null`
- which operational behaviors matter in production

## 2. Quick recommendations

If you only want the short version, keep these points in mind:

1. Prefer centralized mode unless you explicitly need distributed deployment.
2. Use a UTF8 GaussDB database.
3. Keep `require_scoped_filters=True` in multi-tenant production environments.
4. Use `metadata_schema` when you want true typed range behavior.
5. Treat `analyze()` as an optional maintenance helper, not a normal request-path call.
6. Assume cross-provider score comparison is invalid.

## 3. Minimal setup

### 3.1 Install the Python package

```bash
pip install mem0ai
```

For local development in this repository:

```bash
pip install -e ".[vector_stores,llms,nlp]"
```

### 3.2 Basic configuration

```python
from mem0 import Memory

config = {
    "vector_store": {
        "provider": "gaussdb",
        "config": {
            "host": "127.0.0.1",
            "port": 19995,
            "database": "postgres",
            "user": "lxm",
            "password": "Gauss_234",
            "collection_name": "mem0_prod",
            "embedding_model_dims": 1536,
            "deployment_mode": "centralized",
        },
    }
}

memory = Memory.from_config(config)
```

You can also use `connection_string` instead of separate connection fields.

## 4. Recommended production baseline

Recommended defaults for most production deployments:

```python
{
    "vector_store": {
        "provider": "gaussdb",
        "config": {
            "connection_string": "postgresql://user:password@host:19995/postgres",
            "collection_name": "mem0_prod",
            "embedding_model_dims": 1536,
            "deployment_mode": "centralized",
            "vector_index_type": "gsdiskann",
            "vector_metric": "cosine",
            "minconn": 1,
            "maxconn": 5,
            "auto_create": True,
            "require_scoped_filters": True,
        },
    }
}
```

## 5. Optional advanced configuration

### 5.1 Custom schema

The provider defaults to `public`, but you can override it:

```python
"config": {
    "connection_string": "postgresql://user:password@host:19995/postgres",
    "collection_name": "mem0_prod",
    "schema": "mem0_app",
}
```

If the schema does not exist, the provider attempts to create it during collection creation.

### 5.2 Metadata schema

Use `metadata_schema` when you want controlled typed behavior:

```python
"metadata_schema": {
    "priority": "number",
    "created_at": "datetime",
    "flag": "bool",
    "category": "string",
}
```

Supported declarations:

- `string`
- `text`
- `number`
- `bool`
- `datetime`

## 6. UTF8 recommendation

The GaussDB provider is designed with UTF8 as the recommended database baseline.

Current implementation behavior:

- every connection sets `client_encoding=UTF8`
- the provider checks `server_encoding`
- if the database server is not UTF8, the provider logs a warning

Why this matters:

- Mem0 payloads are JSON-heavy
- multilingual memory text is common
- text filters and keyword search are much safer in UTF8 databases

Recommended rule:

> Use a UTF8 database for supported and production-ready Mem0 deployments on GaussDB.

## 7. Centralized vs distributed

### 7.1 Centralized mode

Centralized mode is the recommended deployment mode.

It supports:

- vector CRUD
- semantic search
- `search_batch`
- metadata filters
- scoped reads
- centralized BM25 `keyword_search`
- typed exact metadata filters
- controlled typed range

### 7.2 Distributed mode

Distributed mode is intentionally narrower.

It supports the core vector-store paths, but BM25 / `keyword_search` is not part of the distributed contract.

## 8. Scoped filtering

### 8.1 Default behavior

`require_scoped_filters=True` by default.

That means these read paths require at least one valid positive scope filter:

- `search`
- `keyword_search`
- `search_batch`
- `list`

Scope fields are:

- `user_id`
- `agent_id`
- `run_id`

### 8.2 Valid examples

These are valid positive scope filters:

```python
{"user_id": "u1"}
{"user_id": {"eq": "u1"}}
{"user_id": {"in": ["u1", "u2"]}}
```

These are not valid positive scope filters:

```python
{"user_id": {"ne": "u1"}}
{"$not": [{"user_id": "u1"}]}
{"$or": [{"user_id": "u1"}, {"category": "public"}]}
{"user_id": "*"}
```

### 8.3 When to keep it enabled

Keep `require_scoped_filters=True` when:

- the deployment is multi-tenant
- you want provider-level safety against broad accidental reads
- the application maps memories to users, agents, or runs

### 8.4 When you may disable it

You may consider disabling it only for:

- controlled diagnostics
- trusted maintenance tools
- isolated data migration tasks
- test harnesses

When disabled, the provider no longer requires a scope on read paths, but all other filter rules still apply.

## 9. Metadata filter behavior

### 9.1 Typed exact behavior

The provider supports:

- `eq`
- `ne`
- `in`
- `nin`

These now behave correctly for:

- string
- number
- bool
- null

### 9.2 Wildcard

For ordinary metadata fields:

```python
{"category": "*"}
```

This means: do not constrain `category` by value.

For scope fields, wildcard still does **not** count as a valid positive scope.

### 9.3 Exists, missing, and null

The provider distinguishes these three cases:

- field exists
- field is missing
- field exists and its value is JSON null

Examples:

```python
{"optional": {"exists": True}}
{"optional": {"missing": True}}
{"optional": None}
```

## 10. Range filters

### 10.1 Declared fields

If a field is declared as `number` or `datetime` in `metadata_schema`, the provider performs real typed range behavior.

Examples:

```python
{"priority": {"gte": 3, "lt": 10}}
{"created_at": {"lt": "2026-01-01T00:00:00Z"}}
```

### 10.2 Undeclared fields

If the field is not declared for typed range:

- the provider does not fail the query
- it emits a warning
- it falls back to compatibility literal matching

This behavior is intentionally closer to the current Mem0 provider ecosystem.

### 10.3 Dirty historical rows

For declared `number` and `datetime` fields, malformed rows are ignored instead of causing the whole query to fail.

This keeps search stable while still honoring typed range semantics for valid rows.

## 11. Score semantics

The provider returns raw distance.

That means:

- smaller distance is better
- the value is backend-metric dependent
- it should not be compared across providers

This aligns GaussDB more closely with other SQL-style providers instead of making it the only normalized-score special case.

## 12. Keyword search

### 12.1 Centralized mode

Centralized mode can support `keyword_search()` through BM25.

### 12.2 Distributed mode

Distributed mode does not promise BM25 / `keyword_search()` support.

If your workflow requires keyword retrieval, plan centralized deployment.

## 13. Maintenance helper: `analyze()`

`analyze()` is available as an auxiliary maintenance interface.

Use cases:

- after collection creation
- after large bulk imports
- during off-peak maintenance
- diagnostics or test runs

Do **not** treat it as a normal high-frequency application-path operation.

## 14. Troubleshooting

### The provider warns about non-UTF8 server encoding

Meaning:

- the database is not using UTF8
- the provider can still try to connect
- text, JSON, metadata filtering, or keyword retrieval may be unstable

Recommended action:

- use a UTF8 database for production deployments

### Range query does not behave as expected

Check:

- whether the field is declared in `metadata_schema`
- whether the declaration is `number` or `datetime`
- whether the stored values are valid for that declared type

### Scoped read error

Check:

- whether you passed at least one positive `user_id`, `agent_id`, or `run_id`
- whether your scope expression uses a real narrowing operator rather than `ne`, `not`, or a loose `or`

### BM25 not available in distributed mode

That is expected under the current distributed capability statement.

## 15. Practical rollout advice

For the cleanest rollout:

1. start with centralized mode
2. use a UTF8 database
3. keep `require_scoped_filters=True`
4. declare `metadata_schema` only for fields that really need typed range semantics
5. validate with the GaussDB commercial validation tests before production traffic
