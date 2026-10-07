# Gotchas — the things that aren't a clean 1:1

Swapping `Memory` for `MemoryClient` is mostly mechanical. These items are *not* mechanical: they
change behavior, move responsibility off the developer's machine, or have no direct equivalent.
Every one that applies to the project belongs in the plan's **"Concerns & decisions needed"**
section, phrased as a decision for the developer — never silently resolved.

## 1. Data does not migrate with the code
Migrating the *code* does not move the *memories*. Anything stored in the local vector store /
history DB stays there; the hosted account starts empty. This is the most surprising gap, so call
it out prominently. Data migration is **out of scope** unless the developer explicitly asks. If they
do, treat it as a separate, opt-in task:
- **Hosted Qdrant + Python OSS SDK:** the repo ships `scripts/oss-to-platform-migrate.sh`
  (`curl -fsSL https://raw.githubusercontent.com/mem0ai/mem0/main/scripts/oss-to-platform-migrate.sh | bash`,
  documented at https://docs.mem0.ai/migration/oss-to-platform). It needs `python3`, signs in to the
  Platform (`--email`/`--code` or `--api-key`), exports a scope (`--user-id`, `--agent-id`, `--run-id`
  or `--all`) from the Qdrant collection (`--qdrant-url`, `--qdrant-api-key`, `--qdrant-collection`,
  default `mem0`) to a JSON file under `~/.mem0/migrations/`, and imports it with `infer: False` (stored
  verbatim, no re-extraction). `--export-only` / `--import-only` split the two steps so the export can
  be reviewed first. Don't run it unprompted: it logs in and writes under `~/.mem0/`.
- **Anything else:** other vector stores are not supported by the script (the docs say hosted Qdrant
  only), and its export is written for the Python OSS SDK, so TS-written data is not documented as
  supported. The fallback is to read everything from the OSS store (`get_all` per entity) and re-`add`
  it with `infer=False`.

## 2. Self-hosting / data residency
A local or self-hosted vector store sometimes exists *on purpose* — compliance, data residency, air-
gapped deployment, cost. Moving to the managed platform sends memory content to mem0's servers.
Don't assume that's acceptable; flag it as an explicit decision, especially for regulated domains.

## 3. Local models move server-side
If the OSS config used specific local/self-chosen models (e.g. Ollama, a particular embedder, a
non-OpenAI LLM for fact extraction), those choices disappear — extraction and embedding now run on
the platform with the platform's configuration. Memory *content and quality may shift* as a result.
Flag where the project depended on a specific model.

## 4. Graph memory
The external graph store (`graph_store`, `enable_graph`; Neo4j/Memgraph/Kuzu/AGE) was removed from OSS
(Python 2.0.0, TS 3.0.0). On the platform graph memory is built in and always on: nothing to enable or
configure, and it only influences ranking (no separate `relations` payload, no typed relationships,
no direct graph queries). Flag any project code that queried its own graph store or read `relations`.
See https://docs.mem0.ai/platform/features/graph-memory.

## 5. Custom prompts / extraction config
`custom_fact_extraction_prompt` (TS `customPrompt`) was renamed `custom_instructions`
(`customInstructions`), and `custom_update_memory_prompt` is deprecated (fold it into
`custom_instructions`). On the platform `custom_instructions` is a project-level setting:
`client.project.update(custom_instructions=...)` (TS `client.updateProject({ customInstructions })`),
or per call via `custom_instructions=` on `add()`.
Flag any custom prompt the project relied on so the developer can decide where to re-apply it.

## 6. Every call is now a network request
Local calls become remote API calls. That introduces latency, network failures, timeouts, rate
limits, and per-call cost. Flag mem0 calls on hot paths or in tight loops, and recommend adding
error handling / retries / timeouts where the old local calls were effectively infallible. For async
apps, use `AsyncMemoryClient` (Python) so calls don't block the event loop.

## 7. API key & secrets
The hosted client needs `MEM0_API_KEY`. It must come from the environment / a secrets manager, never
hardcoded. Ensure it's added to `.env.example`, local `.env`, CI, and deployment config. Without it
the client fails to initialize. The Python client reads `MEM0_API_KEY` itself when `api_key` is
omitted; the TS client does not, so pass `apiKey: process.env.MEM0_API_KEY!` explicitly.

## 8. Dropped constructor args & legacy options
`org_id` / `project_id` (Python) and `organizationId` / `projectId` (TS) are no longer passed to the
constructor, they're resolved from the API key. Per-call legacy options like `async_mode`,
`output_format`, and `enable_graph` are gone. Remove them rather than leaving dead args.

## 9. Return-shape and default drift
- `add()` is **asynchronous** on the platform: it returns `{"status": "PENDING", "event_id": "..."}`
  (`eventId` on the TS client, which camelCases response keys) instead of the created memories, so new memories may not be searchable yet when it returns
  (`infer=False` is synchronous and returns `results`). Code that read `id`/`memory` from `add()`
  results, or searched immediately after adding (tests, read-your-writes flows), needs a decision.
  Neither SDK exposes an event-poll method; `GET /v1/event/{event_id}/` is REST only.
- `search` returns `{"results": [...]}` on both sides; `get_all` is paginated on the platform
  (`count`/`next`/`previous`/`results`). Code that limited via `top_k` on `get_all` should move to
  `page`/`page_size` (default `page_size` 100).
- Defaults differ: OSS `search` uses `top_k=20`, the platform uses `top_k=10`. Both default to
  `rerank=false`. OSS `threshold` defaults to 0.1; on the platform it is a server-side cutoff, not a floor on the returned `score`. Result counts can change even when the call looks equivalent;
  pass `top_k` explicitly.

## 10. `reset()` is much more destructive
The OSS `reset()` wipes the local store. Python `MemoryClient.reset()` exists but calls `delete_users()`,
which deletes all users, agents, sessions and memories on the platform. The TS client has no `reset()`
(`deleteUsers()` with no arguments does the same). Flag any `reset()` call (often test teardown) and
suggest `delete_all` scoped to the test entity instead. `delete_all(filters=...)` is not a valid
platform form: pass `user_id`/`agent_id`/`app_id`/`run_id` directly.

The hosted wipe is also incomplete: Python `reset()` and TS `deleteUsers()` with no arguments call
`users()` once and delete only the entities on that first page, so a project with more entities than
one page keeps the rest. Re-run until it raises `No entities to delete`, or delete per entity
(`delete_users(user_id=...)` / `deleteUsers({ userId })`, paging TS with `users({ page, pageSize })`).

## 11. Filters and update/add signatures
- Platform `filters` only accept an allowlist of top-level keys; custom metadata must be nested under
  `"metadata"` and supports only `eq`/`ne`/`contains` (whole value or list member, not a substring; no `nin`; use a `NOT` list, e.g. `{"NOT": [{"categories": {"in": [...]}}]}`). OSS filters on arbitrary metadata
  keys or richer operators need rewriting or a decision.
- Python `update` takes `text=` as a keyword (a positional string breaks); TS `update` requires an
  options object and TS `add` requires `Message[]`, not a bare string.
