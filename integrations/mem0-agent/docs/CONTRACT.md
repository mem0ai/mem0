# The Mem0 platform contract, as verified

Everything here was executed against the live API on 2026-07-28 in an isolated scratch
project. Where this document and the published docs disagree, **this document is right** —
each disagreement is marked and was reproduced.

## Four rules that apply to every call

### 1. Pin the project in the request BODY

```python
body = {..., "project_id": "proj_...", "org_id": "org_..."}   # routes correctly
params = {"project_id": "proj_..."}                           # SILENTLY IGNORED
```

The API key carries a default project. Passing `project_id` as a query param does not
override it — the call lands in the key's default project with no error. Two identical
probe writes, one routed each way, landed in two different projects.

This is almost certainly how v1's benchmark corpora (39% of the production project) got
there. `Api._pin()` applies this automatically; `strict=True` raises if it cannot.

### 2. Every read passes `latest_only=True`

When a fact is contradicted, the platform stores a new memory and supersedes the old one —
but **both are returned** unless you ask for the latest only.

```
get_all(...)                    -> ["deploys on Fly.io", "moved off Fly.io to Railway"]
get_all(..., latest_only=True)  -> ["moved off Fly.io to Railway"]
```

Serving both is exactly the "relitigated decisions" failure this product exists to fix.
Works identically on `search`. `Api.get_all/search` default it to `True`.

### 3. Type lives in `metadata.type`, not `categories`

Categorization is a background job, measured against 10 days of production data:

| Memory age | Categorized |
|---|---|
| < 1 hour | **0%** (0 of 22) |
| 6–24 hours | 100% |
| 1–3 days | 95.1% |
| > 3 days | 92.8% |

Median write→categorize lag **3.9 hours**, p90 ≈ 72 hours, and ~5–7% never get categorized.
So a morning session's learnings would be invisible to an afternoon context pack if reads
filtered on `categories`.

Verified fix: stamp `metadata.type` at write time. Metadata survives `infer=True` extraction
intact (every extracted fact inherits the window's metadata) and is filterable within
seconds. Read recipes `OR` metadata with categories so fresh memories match on metadata and
older ones match either way.

### 4. `NOT` takes a list

```python
{"NOT": [{"app_id": "*"}]}    # 200
{"NOT": {"app_id": "*"}}      # 400   <- the shape shown in the docs
```

## Scoping

| Scope | Written as | Read with |
|---|---|---|
| user (preferences) | `user_id`, **no** `app_id` | `{"AND":[{"user_id":u},{"NOT":[{"app_id":"*"}]}]}` |
| project (everything else) | `user_id` + `app_id` | `{"AND":[{"user_id":u},{"app_id":a}]}` |
| session | `metadata.session_id` | metadata equality filter |

**Documented "implicit null scoping" does not hold.** `{"user_id": u}` alone returns
project-scoped records too, so user-scope reads need the explicit `NOT` clause. Verified:
without it a user-scope query returned 2 records (one of them project-scoped); with it, 1.

**Never use `run_id` or `agent_id`.** Records carry exactly one primary entity, so a
cross-entity `AND` matches nothing. v1 wrote every session summary with `run_id` while no
read path filtered by it — its highest-volume write path was unretrievable.

`app_id` is the git-remote slug (`owner-repo`), stable across clones and worktrees.
Identity comes from `GET /v1/ping/` → `user_email`, `org_id`, `project_id`.

## Writes

- `add(infer=True)` is **fire-and-forget**: the response is `{event_id, status: "PENDING"}`
  with no memory IDs. Extraction landed in **20s–5min** across runs. Never read-after-write
  inside a session; capture happens at boundaries and reads at the next session start.
- `add(infer=False)` (direct import) is immediate — and **stores assistant-role messages
  too**, contrary to the docs which say only user-role messages are kept. Write
  `session_state` as a single user-role message rather than relying on role filtering.
- `infer=True` deduplicates: the same fact sent twice yields one record.
- `metadata` on the add call propagates to every fact extracted from that window.

## Lifecycle

- `expiration_date` (`YYYY-MM-DD`, UTC, inclusive) hides a memory from `get_all` **and**
  `search`; `get(memory_id)` still returns it; `show_expired=True` reveals it; setting it to
  `None` restores visibility. Nothing is deleted.
- `decay=True` (project-level) biases ranking by recency-of-use (0.3×–1.5×) and reinforces
  a memory each time it is retrieved. Never filters.
- **Deletes are soft.** Rows persist with `is_deleted=true` and vanish from all reads.
  `delete_all` also renames the entity (`<user>_deleted_<timestamp>`). Migration tooling
  must verify through the API's own reads, not by expecting rows to disappear.

## Endpoint quirks

| Call | Quirk |
|---|---|
| `DELETE /v1/memories/` | Takes **query params**; a body returns 400 "at least one filter required" |
| `GET .../projects/<id>/` | `fields` must be **repeated** params (`?fields=a&fields=b`), not comma-joined |
| `POST /v1/feedback/` | **404s without the project pin** in the body |
| `POST /v3/memories/` | This is `get_all`; `page`/`page_size` are query params, filters go in the body |

## Metadata schema

```json
{
  "type": "preference|decision|convention|insight|runbook|session_state",
  "session_id": "…",
  "branch": "…",
  "editor": "claude-code",
  "policy": "v2.0",
  "pinned": true
}
```

`type` is authoritative at read time. `policy` records which gate revision produced the
memory, so a quality regression can be traced to a config change. `pinned` is the only pin
mechanism — `update` does accept metadata (v1's `[PINNED]` text-prefix hack was based on a
stale assumption, and its consolidation step never honored it anyway).

## What the write gate catches, and what it cannot

Fed the actual v1 pollution, the custom instructions suppress: training heartbeats,
progress/ETA spam, file-modification lists, session-only narration, and one-off task
directives.

The one class instructions **cannot** filter is **repository file content**. A CLAUDE.md
excerpt of coding standards was extracted as three preferences, because provenance is
invisible to the extractor and that text is indistinguishable from a genuine project
convention — which must stay extractable. Client-side omission is the only enforcement,
and it is why v1's auto-import feature is retired outright.
