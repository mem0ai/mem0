# Mem0 GaussDB Technical Design

> Updated: 2026-05-18  
> Main code: `mem0/vector_stores/gaussdb.py`, `mem0/configs/vector_stores/gaussdb.py`

## 1. Design goal

The GaussDB provider is designed to make GaussDB behave like a serious Mem0 vector store, not just a thin SQL compatibility adapter.

The design goals are:

1. preserve the existing Mem0 provider contract
2. provide a strong centralized deployment story
3. keep distributed behavior explicit and honest
4. support stable scoped filtering and metadata filtering
5. avoid fake support for capabilities that the provider cannot implement correctly

## 2. High-level architecture

The provider sits under the standard Mem0 memory layer.

```text
Memory / AsyncMemory
  -> vector store factory
    -> GaussDBConfig
    -> GaussDB provider
       -> connection pool
       -> capability checks
       -> collection lifecycle
       -> filter compiler
       -> vector / keyword search
```

The provider is responsible for translating Mem0 operations into GaussDB-specific SQL, while preserving Mem0 expectations as closely as possible.

## 3. Configuration model

### 3.1 Base connection configuration

The provider accepts either:

- a full `connection_string`
- or `host`, `port`, `database`, `user`, and `password`

Optional connection settings:

- `sslmode`
- `sslrootcert`
- `minconn`
- `maxconn`

### 3.2 Deployment and vector configuration

Important provider options:

- `deployment_mode`: `centralized` or `distributed`
- `vector_index_type`: `gsdiskann` or `gsivfflat`
- `vector_metric`: `cosine` or `l2`
- `embedding_model_dims`
- `collection_name`
- `schema` (advanced, default `public`)

### 3.3 Advanced behavior configuration

Additional advanced options:

- `auto_create`
- `require_scoped_filters`
- `metadata_schema`

`metadata_schema` is used to declare fields that should receive typed behavior, especially for controlled range support.

Example:

```python
metadata_schema = {
    "priority": "number",
    "created_at": "datetime",
    "flag": "bool",
    "category": "string",
}
```

## 4. Connection handling

### 4.1 Pooling

The provider uses `ThreadedConnectionPool`.

Default bounds:

- `minconn=1`
- `maxconn=5`

This is intentionally conservative and aligns with the style of other SQL-oriented providers in Mem0.

### 4.2 UTF8 session handling

Every connection is configured with `client_encoding=UTF8`.

In addition, initialization checks the database `server_encoding`. If the server is not UTF8, the provider logs a warning instead of blocking startup.

This gives the best tradeoff for Mem0:

- UTF8 remains the recommended deployment baseline
- historical non-UTF8 environments are surfaced early
- the provider stays usable for controlled diagnostics or migration scenarios

## 5. Schema and collection model

### 5.1 Default schema

The provider now supports an optional `schema` configuration value.

- default: `public`
- custom schema: allowed when the identifier is safe

If the configured schema does not exist, the provider attempts to create it during collection creation.

### 5.2 Single-provider-instance / single-collection model

A provider instance is bound to one logical collection table.

That means:

- one `collection_name`
- one main table
- one schema metadata table

The provider does not support implicit table switching inside the same instance.

## 6. Main table design

The collection table stores:

- `id`
- `vector`
- `payload`
- `memory`
- `text_lemmatized`
- `created_at`
- `updated_at`
- `user_id`
- `agent_id`
- `run_id`

The important design change is that `user_id`, `agent_id`, and `run_id` are treated as first-class columns rather than only implicit payload-derived metadata.

That gives the provider:

- stronger scoped filtering
- clearer indexing
- cleaner delivery semantics for multi-tenant deployments

## 7. Collection lifecycle

### 7.1 Creation

Collection creation is responsible for:

- ensuring the target schema exists
- creating the main collection table
- creating the schema metadata table
- creating the vector index
- creating scoped indexes
- creating BM25 structures when centralized BM25 is enabled

### 7.2 Reset and deletion

The provider supports:

- `reset()`
- `delete_col()`
- `list_cols()`
- `col_info()`

`list_cols()` remains a management-oriented helper, not a hard security boundary.

## 8. Capability and environment checks

The provider performs environment checks to validate whether the target deployment supports the features it wants to use.

The exact probes are less important than the principle:

- prefer explicit capability checks
- fall back gracefully when safe
- do not silently pretend a feature exists when it does not

## 9. Insert and upsert path

The provider uses `MERGE INTO` for atomic upsert behavior.

Why this matters:

- avoids split `UPDATE + INSERT` races
- maps well to the target GaussDB environment
- gives predictable behavior under concurrent writes

Insert / upsert also keeps scoped columns synchronized with the payload.

## 10. Filter engine design

This is the most important part of the current provider design.

### 10.1 Scope guard

`require_scoped_filters=True` by default.

The provider requires a positive scoped filter for these read paths:

- `search`
- `keyword_search`
- `search_batch`
- `list`

Accepted scope keys:

- `user_id`
- `agent_id`
- `run_id`

Positive scope examples:

- `{"user_id": "u1"}`
- `{"user_id": {"eq": "u1"}}`
- `{"user_id": {"in": ["u1", "u2"]}}`

Rejected as non-positive scope:

- `{"user_id": {"ne": "u1"}}`
- `{"$not": [{"user_id": "u1"}]}`
- `{"$or": [{"user_id": "u1"}, {"category": "public"}]}`
- `{"user_id": "*"}`

### 10.2 Typed exact filters

The provider supports stable scalar semantics for:

- `eq`
- `ne`
- `in`
- `nin`

Supported scalar families:

- string
- number
- bool
- null

This is a major improvement over broad `str(value)` coercion used by simpler SQL-style providers.

### 10.3 Wildcard

For ordinary metadata fields:

- `{"field": "*"}` means: do not constrain the field value

For scope fields:

- `*` does not count as a valid positive scope

### 10.4 Exists, missing, and null

The provider distinguishes:

- field exists
- field missing
- field exists with JSON null

This distinction is explicit rather than accidental.

### 10.5 Typed range

The provider supports controlled typed range for fields declared in `metadata_schema` as:

- `number`
- `datetime`

Examples:

```python
{"priority": {"gte": 3, "lt": 10}}
{"created_at": {"lt": "2026-01-01T00:00:00Z"}}
```

#### Undeclared fields

For undeclared fields, the provider does not hard-fail.

Instead it:

- emits a warning
- falls back to compatibility literal matching

This keeps the behavior closer to the current Mem0 provider ecosystem while preserving stronger typed behavior where explicitly declared.

#### Dirty rows in declared ranges

For declared `number` and `datetime` fields, malformed rows are ignored rather than causing the entire query to fail.

That is the right search-path tradeoff:

- typed semantics for valid rows
- graceful handling of historical bad data

### 10.6 Text operators

The provider supports:

- `contains`
- `icontains`

These remain text-oriented operators. They are intentionally separate from typed exact and typed range behavior.

## 11. Search behavior

### 11.1 Semantic search

The provider uses the configured vector metric:

- `cosine`
- `l2`

### 11.2 Score semantics

The provider now returns raw distance.

This is intentional.

GaussDB no longer applies provider-specific score normalization because that made it a special case among Mem0 providers without solving cross-provider score comparability.

Result:

- smaller distance is better
- score values still should not be compared across different providers

### 11.3 Keyword search

In centralized mode, the provider can use BM25 for `keyword_search`.

In distributed mode, BM25 is disabled by design and `keyword_search` is not part of the distributed capability promise.

### 11.4 Batch search

`search_batch()` is implemented and treated as a real provider capability, not just a convenience wrapper.

## 12. Maintenance interface

### 12.1 `analyze()`

`analyze()` is intentionally kept as an auxiliary maintenance interface.

It is not a core Mem0 application-path capability.

Its design characteristics:

- uses autocommit
- suitable after collection creation, bulk import, or manual maintenance
- should not be called on hot business paths

This position aligns better with the broader Mem0 provider ecosystem, where most providers do not expose an explicit maintenance operation of this kind.

## 13. Operational defaults

### 13.1 UTF8-first

Recommended and supported baseline:

- UTF8 database
- UTF8 client session

### 13.2 Vector index maintenance memory

The provider raises session-local `maintenance_work_mem` only when required and only when the current value is lower than the target.

For high-dimensional index build paths, this avoids both under-provisioning and unnecessary downscoping of already larger DBA settings.

### 13.3 Schema default

The provider defaults to `public`, but allows an advanced `schema` override.

## 14. Testing model

The current branch uses layered validation:

1. provider unit tests
2. commercial validation tests
3. centralized live validation
4. distributed validation when an internal distributed environment is available

This matters because the provider includes behavior that is easier to reason about than to guarantee without real database execution, especially around:

- BM25 behavior
- scoped filtering
- range behavior on dirty data
- connection/session configuration

## 15. Final design assessment

The current GaussDB provider is no longer a thin fork of an older SQL-style implementation.

Its main design qualities are:

- explicit scoped-read model
- stronger typed exact semantics
- controlled typed range semantics
- raw-distance score alignment with other SQL-style providers
- UTF8-first operational posture
- centralized-first commercial story

The result is a provider that is much easier to review, explain, and operate in a real Mem0 deployment.
