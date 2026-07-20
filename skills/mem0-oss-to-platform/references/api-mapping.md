# OSS → Platform API mapping

Exact translation of the mem0 OSS (self-hosted `Memory`) API to the hosted `MemoryClient` API.
**Always confirm against the installed package** (see SKILL.md Phase 2) — versions drift. The facts
below match `mem0ai` 2.0.x (the v3 platform API) and the official guide:
https://docs.mem0.ai/migration/oss-v2-to-v3

## Contents
- [Python](#python)
- [TypeScript / JavaScript](#typescript--javascript)
- [Return shapes](#return-shapes)
- [Dependencies & environment](#dependencies--environment)
- [v2→v3 default/behavior changes](#v2v3-defaultbehavior-changes)

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
- **Drop** `vector_store`, `llm`, `embedder`, `graph_store`, `history_db_path` — these are managed
  server-side now.
- **Drop** `org_id` / `project_id` constructor args if present — they're resolved from the API key
  in v3.
- For async codebases, use `AsyncMemoryClient` (same methods, `await`-ed).

### Method calls
| Operation | OSS `Memory` | Hosted `MemoryClient` |
|---|---|---|
| add | `memory.add(messages, user_id="u")` | `memory.add(messages, user_id="u")` — unchanged (top-level entity IDs accepted) |
| search | `memory.search(q, user_id="u", limit=N)` *(older)* or `…, filters={"user_id":"u"}, top_k=N` *(newer)* | `memory.search(q, filters={"user_id": "u"}, top_k=N)` — entity IDs **must** be inside `filters`; top-level `user_id`/`agent_id`/`app_id`/`run_id` raise `ValueError` |
| get_all | `memory.get_all(user_id="u")` or `…, filters={"user_id":"u"}` | `memory.get_all(filters={"user_id": "u"}, page=1, page_size=N)` — entity IDs in `filters`; paginated with `page`/`page_size` (**not** `top_k`) |
| delete_all | `memory.delete_all(user_id="u")` | `memory.delete_all(user_id="u")` — unchanged |
| get | `memory.get(memory_id)` | `memory.get(memory_id)` |
| update | `memory.update(memory_id, text=...)` *(`data=` is a deprecated alias)* | `memory.update(memory_id, text=...)` — unchanged |
| delete | `memory.delete(memory_id)` | `memory.delete(memory_id)` |
| reset | `memory.reset()` (wipes the local store) | **No global reset.** Use `memory.delete_all(filters=...)` scoped to the relevant entity. Flag this. |

Key rule: for **search** and **get_all**, the hosted client requires entity IDs (`user_id`,
`agent_id`, `app_id`, `run_id`) inside a `filters` dict and will raise if you pass them top-level.
For **add** and **delete_all**, top-level entity IDs are accepted.

---

## TypeScript / JavaScript

The hosted and OSS SDKs ship in the same `mem0ai` npm package, distinguished by import path.
Confirm option names against `node_modules/mem0ai/` types.

### Import & client construction
```typescript
// OSS (self-hosted) — note the "/oss" subpath
import { Memory } from "mem0ai/oss";
const memory = new Memory({ /* vectorStore, embedder, llm, historyStore … */ });

// Platform (hosted) — default export from the package root
import MemoryClient from "mem0ai";
const memory = new MemoryClient({ apiKey: process.env.MEM0_API_KEY });
// Drop organizationId / projectId — resolved from the API key in v3.
```

### Method calls (option-object differences)
| Operation | OSS / old client | Hosted client (v3) |
|---|---|---|
| add | `memory.add(messages, { userId: "u" })` | `memory.add(messages, { userId: "u" })` — unchanged |
| search | `memory.search(q, { userId: "u", limit: 20 })` | `memory.search(q, { filters: { userId: "u" }, topK: 20 })` — entity IDs into `filters`; `limit` → `topK` |
| getAll | `memory.getAll({ userId: "u" })` | `memory.getAll({ filters: { userId: "u" } })` — entity IDs into `filters` |
| deleteAll | `memory.deleteAll({ userId: "u" })` | `memory.deleteAll({ userId: "u" })` |
| get / update / delete | `memory.get(id)` etc. | same, by memory id |

Also drop legacy options that no longer apply on v3: `async_mode`, `output_format`, `enable_graph`.

---

## Return shapes
- `search(...)` and `get_all(...)` return `{"results": [...]}`; each item has at least a `memory`
  (text) field, plus `id` and (for search) `score`. Code that reads `result["results"]` and pulls
  `item["memory"]` keeps working.
- `get_all(...)` on the hosted client is paginated: `{"count", "next", "previous", "results": [...]}`.
- `add(...)` returns the created memories. On v3 it returns **only ADD events** — if the old code
  branched on `event == "UPDATE"` / `"DELETE"` from `add()` results, that branch is now dead.

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

## v2→v3 default/behavior changes
From the official migration guide — surface any that affect the project:
- Python `top_k` default changed 100 → 20; TS `limit` renamed to `topK`.
- New `threshold` default `0.1` (was none); new `rerank` default `false` (was true).
- `custom_fact_extraction_prompt` → `custom_instructions`; `custom_update_memory_prompt` deprecated.
- Graph memory (`enable_graph`, `graph_store`) removed from the OSS v3 surface — see gotchas.
