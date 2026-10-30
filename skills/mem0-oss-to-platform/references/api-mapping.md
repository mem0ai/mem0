# OSS → Platform API mapping

Exact translation of the mem0 OSS (self-hosted `Memory`) API to the hosted `MemoryClient` API.
**Always confirm against the installed package** (see SKILL.md Phase 2), since versions drift. The
facts below match Python `mem0ai` 2.2.x and TypeScript `mem0ai` 3.3.x (the `/v3/memories/*` platform
API). Moving stored data: https://docs.mem0.ai/migration/oss-to-platform. OSS upgrade changes
(Python 1.x to 2.x, TS 2.x to 3.x): https://docs.mem0.ai/migration/oss-v2-to-v3

## Contents
- [Python](#python)
- [TypeScript / JavaScript](#typescript--javascript)
- [Return shapes](#return-shapes)
- [Dependencies & environment](#dependencies--environment)
- [OSS vs Platform defaults and behavior](#oss-vs-platform-defaults-and-behavior)

---

## Python

### Import & client construction
```python
# OSS (self-hosted)
from mem0 import Memory
memory = Memory()                       # or:
memory = Memory.from_config({           # all of this local config disappears
    "vector_store": {...},
    "llm": {...},
    "embedder": {...},
    "history_db_path": "...",
})

# Platform (hosted)
from mem0 import MemoryClient
memory = MemoryClient()                 # reads MEM0_API_KEY from the env
# or: MemoryClient(api_key="...")
```
Notes:
- The client reads `MEM0_API_KEY` from the environment when `api_key` is omitted.
- **Drop** `vector_store`, `llm`, `embedder`, `reranker`, `history_db_path`, `version` (and
  `graph_store` if a pre-2.0 config still has it): these are managed server-side now.
- `custom_instructions` does have a hosted equivalent: `client.project.update(custom_instructions=...)`
  (project-wide) or `custom_instructions=` on `add()`.
- **Drop** `org_id` / `project_id` constructor args if present, they're resolved from the API key.
- For async codebases, use `AsyncMemoryClient` (same methods, `await`-ed).

### Method calls
| Operation | OSS `Memory` | Hosted `MemoryClient` |
|---|---|---|
| add | `memory.add(messages, user_id="u")` | `memory.add(messages, user_id="u")`: same call (top-level entity IDs accepted, plus `app_id`), but the return value differs (see Return shapes) |
| search | `memory.search(q, filters={"user_id": "u"}, top_k=N)` (pre-2.0 code used top-level `user_id=` and `limit=`) | `memory.search(q, filters={"user_id": "u"}, top_k=N)`: entity IDs **must** be inside `filters`; top-level `user_id`/`agent_id`/`app_id`/`run_id` raise `ValueError` (on OSS 2.x too) |
| get_all | `memory.get_all(filters={"user_id": "u"}, top_k=N)` (not paginated) | `memory.get_all(filters={"user_id": "u"}, page=1, page_size=N)`: entity IDs in `filters`; paginated with `page`/`page_size` (**not** `top_k`) |
| delete_all | `memory.delete_all(user_id="u")` | `memory.delete_all(user_id="u")`: same call (entity IDs are query params, at least one is required, `"*"` is a wildcard). `delete_all(filters=...)` is **not** a Platform form |
| get | `memory.get(memory_id)` | `memory.get(memory_id)` |
| update | `memory.update(memory_id, text=...)` *(`data=` is a deprecated alias)* | `memory.update(memory_id, text=..., metadata=...)`: use keyword `text=`. A positional string (`update(id, "new text")`) breaks because the second positional is `options`, and there is no `data=` alias |
| delete | `memory.delete(memory_id)` | `memory.delete(memory_id)` |
| history | `memory.history(memory_id)` | `memory.history(memory_id)`: same call, extra fields on each entry (`input`, `user_id`, `categories`, `metadata`); OSS-only `is_deleted`/`actor_id`/`role` are absent (see Return shapes) |
| reset | `memory.reset()` (wipes the local store) | `memory.reset()` exists but calls `delete_users()`, which deletes **all** users, agents, sessions and memories (first page of entities only, see gotchas). Prefer `delete_all` scoped to an entity. Flag this |

Key rule: for **search** and **get_all**, the hosted client requires entity IDs (`user_id`,
`agent_id`, `app_id`, `run_id`) inside a `filters` dict and will raise if you pass them top-level.
For **add** and **delete_all**, top-level entity IDs are accepted.

Filter differences: Platform validates each top-level filter key against a fixed allowlist
(`AND`/`OR`/`NOT`, `user_id`, `agent_id`, `app_id`, `run_id`, `created_at`, `updated_at`, `timestamp`,
`expiration_date`, `categories`, `metadata`, `memory_ids`, `keywords`) and
returns 400 for anything else, so custom metadata keys must be nested under `"metadata"`
(`{"metadata": {"plan": "pro"}}`). Platform `metadata` supports only `eq`/`ne`/`contains` (`contains` is case-sensitive and matches the whole value or one list member, not a substring), and there is
no `nin` (use `{"NOT": [{"categories": {"in": [...]}}]}`; `NOT` must be a list). OSS accepts arbitrary
metadata keys and a wider operator set. Flag any OSS filter that depends on either. Do not filter on `text`: search fails with a 503 and `get_all` rejects it. Pass the text as the search `query`.

---

## TypeScript / JavaScript

The hosted and OSS SDKs ship in the same `mem0ai` npm package, distinguished by import path.
Confirm option names against `node_modules/mem0ai/` types.

### Import & client construction
```typescript
// OSS (self-hosted): note the "/oss" subpath
import { Memory } from "mem0ai/oss";
const memory = new Memory({ /* vectorStore, embedder, llm, historyStore, reranker, customInstructions … */ });

// Platform (hosted): default export from the package root
import MemoryClient from "mem0ai";
const memory = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });
```
Notes:
- Unlike Python, the TS client does **not** read `MEM0_API_KEY` itself: `apiKey` is required and the
  constructor throws if it is empty. Pass it explicitly.
- Drop `organizationId` / `projectId` if present, they're resolved from the API key.
- Drop `vectorStore`, `embedder`, `llm`, `historyStore`, `historyDbPath`, `reranker`, `disableHistory`,
  `version`. `customInstructions` maps to `client.updateProject({ customInstructions })` or
  `customInstructions` on `add()`.

### Method calls (option-object differences)
| Operation | OSS `Memory` | Hosted client |
|---|---|---|
| add | `memory.add(messages, { userId: "u" })` (`messages` may be a string or `Message[]`) | `memory.add(messages, { userId: "u" })`: `messages` must be `Message[]` (wrap a bare string as `[{ role: "user", content: str }]`); the response is an async event (see Return shapes) |
| search | `memory.search(q, { filters: { user_id: "u" }, topK: 20 })` (pre-3.0 code used top-level `userId` and `limit`) | `memory.search(q, { filters: { user_id: "u" }, topK: 20 })`: entity IDs go inside `filters` with **snake_case** keys (`user_id`, not `userId`); top-level `userId` throws; `limit` → `topK` |
| getAll | `memory.getAll({ filters: { user_id: "u" }, topK: 20 })` (not paginated) | `memory.getAll({ filters: { user_id: "u" }, page: 1, pageSize: 50 })`: paginated with `page`/`pageSize` (not `topK`) |
| deleteAll | `memory.deleteAll({ userId: "u" })` | `memory.deleteAll({ userId: "u" })`: same call (at least one entity ID is required) |
| update | `memory.update(id, "new text")` or `memory.update(id, { text, metadata })` | `memory.update(id, { text: "new text" })`: the options object is required, a bare string throws |
| get / delete / history | `memory.get(id)` etc. | same, by memory id (`history` field names differ, see Return shapes) |
| reset | `memory.reset()` (wipes the local store) | No `reset()` on the TS client. `deleteUsers()` with no arguments deletes all users, agents, sessions and memories (first page of entities only, see gotchas). Prefer `deleteAll` scoped to an entity. Flag this |

Also drop legacy options that no longer apply: `async_mode`, `output_format`, `enable_graph`.

---

## Return shapes
- `search(...)` returns `{"results": [...]}` on both sides; each item has at least a `memory` (text)
  field, plus `id` and `score`. Code that reads `result["results"]` and pulls `item["memory"]` keeps
  working.
- `get_all(...)`: OSS returns `{"results": [...]}` (no pagination). The hosted client is paginated:
  `{"count", "next", "previous", "results": [...]}`.
- `add(...)`: OSS extracts synchronously on both runtimes, but the event sits in a different place:
  Python OSS returns `{"results": [{"id", "memory", "event": "ADD"}]}`, TS OSS returns
  `{ results: [{ id, memory, metadata: { event: "ADD" } }] }` (no top-level `event`).
  The hosted `add` is **asynchronous by default** and returns `{"status": "PENDING", "event_id": "..."}`
  from Python. The TS hosted client camelCases response keys, so it returns
  `{ status: "PENDING", eventId: "..." }` (its typed return `Array<Memory>` does not reflect this).
  New memories may not be searchable yet. Only `infer=False` is synchronous and returns `results`.
  Neither SDK has an event-poll method: poll `GET /v1/event/{event_id}/` over REST if you must wait.
  Code that reads `id`/`memory` from `add()` results must change, and any 1.x-era branch on
  `event == "UPDATE"` / `"DELETE"` is dead on both sides (add is ADD-only since 2.0).
- `history(...)` field names differ on all four runtimes:

  | Runtime | Entry fields |
  |---|---|
  | Python OSS | `id`, `memory_id`, `old_memory`, `new_memory`, `event`, `created_at`, `updated_at`, `is_deleted`, `actor_id`, `role` (oldest first) |
  | TS OSS | `id`, `memory_id`, `previous_value`, `new_value`, `action`, `created_at`, `updated_at`, `is_deleted` (raw rows, snake_case, newest first) |
  | Hosted Python | `id`, `memory_id`, `input`, `old_memory`, `new_memory`, `event`, `user_id`, `categories`, `metadata`, `created_at`, `updated_at` |
  | Hosted TS | `id`, `memoryId`, `input`, `oldMemory`, `newMemory`, `event`, `userId`, `categories`, `metadata`, `createdAt`, `updatedAt` |

  Code that reads `previous_value` / `new_value` / `action` from TS OSS history must switch to
  `oldMemory` / `newMemory` / `event` on the hosted TS client.

---

## Dependencies & environment
- **Keep** the `mem0ai` dependency — `MemoryClient` ships in the same package. No version bump is
  required just to use the hosted client (confirm the installed version supports it).
- **Remove** dependencies that existed *only* to back the local mem0 store/embedder/LLM and are now
  unused (e.g. `qdrant-client`, `chromadb`, a local embedding lib). Only remove what you can confirm
  is unused elsewhere.
- **Add** `MEM0_API_KEY` to the environment / `.env.example` / secrets manager / deployment config.
- Local-infra services (e.g. a Qdrant docker-compose service) that existed only for mem0 can be
  retired — flag this rather than deleting infrastructure unilaterally.

## OSS vs Platform defaults and behavior
Surface any that affect the project. Defaults differ between the two sides even when a call looks
identical:
- `search`: OSS `top_k=20`, `threshold=0.1`, `rerank=False`. Platform `top_k=10` (allowed 1 to 1000),
  `rerank=false`, and `threshold` is a server-side cutoff, not a floor on the returned `score`. Pass `top_k` explicitly to keep the old result count.
- `get_all`: OSS `top_k=20`, not paginated. Platform `page=1`, `page_size=100`.
- `custom_fact_extraction_prompt` (TS `customPrompt`) was renamed `custom_instructions`
  (`customInstructions`) in OSS 2.0/3.0; `custom_update_memory_prompt` is deprecated. See the
  constructor notes for the hosted equivalent.
- Graph memory (`enable_graph`, `graph_store`) was removed from OSS (Python 2.0.0, TS 3.0.0). On the
  Platform graph is built in and always on, with no flag. See gotchas.
- Platform-only: `app_id`, webhooks, custom categories, batch update/delete, feedback, memory export,
  user profiles. `timestamp`, `reference_date` and `decay` raise on OSS.
- OSS-only (no Platform option): `reranker` and `history_db_path` config, `memory_type` and `prompt`
  on `add`, `explain` on `search`.
