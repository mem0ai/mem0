<div align="center">
  <h1>mem0-strands</h1>
  <h3>Persistent long-term memory for Strands Agents, backed by Mem0</h3>
  <p>
    A community <a href="https://strandsagents.com/">Strands Agents</a> integration that plugs
    <a href="https://mem0.ai">Mem0</a> in as a first-class <code>MemoryStore</code>.
  </p>
</div>

---

`mem0-strands` gives [Strands](https://github.com/strands-agents/sdk-python) agents durable memory
that survives across sessions, backed by [Mem0](https://mem0.ai). Where the
`mem0_memory` tool is called explicitly by the model, `Mem0MemoryStore` plugs into the **agent loop**
directly: the manager recalls context and injects it automatically, and writes new memories, either
verbatim or by extracting facts from the conversation.

- **Automatic recall + injection** — relevant memories are searched and prepended to the prompt every turn, no tool call required.
- **Server-side extraction** — raw conversation turns are handed to Mem0, which distills and de-duplicates facts on its own pipeline (no extra client-side model call).
- **Hosted or self-hosted** — the managed [Mem0 Platform](https://app.mem0.ai) by default, or your own Mem0 OSS backend via a config dict.

## Install

```bash
pip install mem0-strands
```

## Usage

```python
from strands import Agent
from strands.memory import MemoryManager
from mem0_strands import Mem0MemoryStore

# Recall + write, distilling facts from the conversation via Mem0's server-side extraction.
store = Mem0MemoryStore(user_id="alex", writable=True, extraction=True)
agent = Agent(memory_manager=MemoryManager(stores=[store]))

# The agent now recalls from and writes to Mem0 without any explicit tool call.
agent("Remember that I prefer dark-mode dashboards and only drink oat milk.")
agent("How do I like my dashboards?")  # recalls the stored preference
```

Set `MEM0_API_KEY` for the hosted platform (get one at [app.mem0.ai](https://app.mem0.ai)), or pass
`api_key=...`. For a self-hosted Mem0 OSS backend, pass a `config=...` dict instead.

## How it works

`Mem0MemoryStore` implements all three `MemoryStore` hooks:

| Method | Maps to | When it runs |
|---|---|---|
| `search(query)` | `mem0.search(query, filters={...})` | Every turn, to recall and inject context |
| `add(content)` | `mem0.add(content, infer=False)` | The `add_memory` tool / a client-side extractor — stores a fact verbatim |
| `add_messages(messages)` | `mem0.add(rendered_turns, infer=True)` | Extraction — renders conversation turns to text, then hands them to Mem0's **server-side** extraction |

Because `add_messages` is implemented, enabling `extraction` routes conversation turns straight to Mem0's own
extraction pipeline. A store that only implemented `add` would instead need a client-side `ModelExtractor`
(an extra model call) to distill facts first.

### Configuration

| Argument | Default | Description |
|---|---|---|
| `user_id` / `agent_id` / `run_id` / `app_id` | _(at least one required)_ | Mem0 entity scope that owns the memories |
| `name` | `"mem0"` | Store identifier, used to target it from memory tools |
| `writable` | `True` | Whether the manager may write to the store |
| `extraction` | `None` | Automatic extraction (`bool` or `ExtractionConfig`) |
| `max_search_results` | `None` | Default result cap per search (falls back to 5) |
| `metadata` | `None` | Default metadata merged into every write |
| `api_key` / `host` | env | Mem0 platform key / base URL (`api_key` defaults to `$MEM0_API_KEY`) |
| `config` | `None` | Mem0 OSS config dict for a self-hosted backend |

## The explicit tool

For the model-called tool (`store` / `retrieve` / `get` / `delete`), use the
[`mem0_memory`](https://github.com/strands-agents/tools) tool from `strands-agents-tools`. The store and
the tool share one Mem0 backend and namespace.

## Telemetry

The store sends anonymous usage events (store configuration, operation, duration,
result counts, coarse failure kind) over the Mem0 SDK's existing telemetry client,
tagged `source="STRANDS"`. Queries, memory text, message content, entity ids, and
metadata are never sent. Turn it off with `MEM0_TELEMETRY=false`.

## Development

The package lives under [`python/`](python/) (monorepo-style layout matching the
[Strands extension-template](https://github.com/strands-agents/extension-template)).

```bash
cd python
pip install hatch
hatch run test        # pytest (no live server required — mocked client)
hatch run prepare     # format + lint + typecheck + test
```

## License

[Apache-2.0](LICENSE). Mem0 is a trademark of its respective owner. Strands Agents is a project of its respective authors.
