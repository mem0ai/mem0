# Gotchas — the things that aren't a clean 1:1

Swapping `Memory` for `MemoryClient` is mostly mechanical. These items are *not* mechanical: they
change behavior, move responsibility off the developer's machine, or have no direct equivalent.
Every one that applies to the project belongs in the plan's **"Concerns & decisions needed"**
section, phrased as a decision for the developer — never silently resolved.

## 1. Data does not migrate with the code
Migrating the *code* does not move the *memories*. Anything stored in the local vector store /
history DB stays there; the hosted account starts empty. This is the most surprising gap, so call
it out prominently. Data migration is **out of scope** unless the developer explicitly asks. If they
do, the rough path is: read everything from the OSS store (`get_all` per user/entity) and re-`add`
it to the hosted client — but treat that as a separate, opt-in task.

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
If the project uses graph memory (`enable_graph`, `graph_store`), this changed in v3 and is handled
differently on the platform. Don't assume a drop-in mapping — verify current platform graph support
in the docs and flag the usage for the developer.

## 5. Custom prompts / extraction config
`custom_fact_extraction_prompt` → `custom_instructions`, and `custom_update_memory_prompt` is
deprecated. On the platform these tend to be **project-level settings configured in the dashboard**
rather than passed in code. Flag any custom prompt the project relied on so the developer can re-
apply it in the dashboard.

## 6. Every call is now a network request
Local calls become remote API calls. That introduces latency, network failures, timeouts, rate
limits, and per-call cost. Flag mem0 calls on hot paths or in tight loops, and recommend adding
error handling / retries / timeouts where the old local calls were effectively infallible. For async
apps, use `AsyncMemoryClient` (Python) so calls don't block the event loop.

## 7. API key & secrets
The hosted client needs `MEM0_API_KEY`. It must come from the environment / a secrets manager — never
hardcoded. Ensure it's added to `.env.example`, local `.env`, CI, and deployment config. Without it
the client fails to initialize.

## 8. Dropped constructor args & legacy options
`org_id` / `project_id` (Python) and `organizationId` / `projectId` (TS) are no longer passed to the
constructor in v3 — they're resolved from the API key. Per-call legacy options like `async_mode`,
`output_format`, and `enable_graph` are gone. Remove them rather than leaving dead args.

## 9. Return-shape drift
- `add()` returns **only ADD events** on v3. Code that inspected `add()` results for `UPDATE` /
  `DELETE` events has dead branches now.
- `search` / `get_all` return `{"results": [...]}`; `get_all` is paginated (`count`/`next`/
  `previous`/`results`). Code that limited via `top_k` on `get_all` should move to `page`/`page_size`.
- Default `top_k` dropped 100 → 20, `threshold` now `0.1`, `rerank` now `false` — result counts and
  ordering can change even when the call looks equivalent.

## 10. No global `reset()`
The OSS `reset()` wipes the whole local store. There's no hosted equivalent that nukes everything;
use `delete_all` scoped by `filters`. Flag any `reset()` call.
