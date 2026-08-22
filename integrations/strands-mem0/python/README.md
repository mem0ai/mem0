# strands-mem0 (Python)

Persistent long-term memory for [Strands Agents](https://github.com/strands-agents/sdk-python),
backed by [Mem0](https://mem0.ai).

See the [repository README](../README.md) for full usage. Quick start:

```bash
pip install strands-mem0
```

As a `MemoryStore` that plugs into the agent loop (Strands >= 1.45):

```python
from strands import Agent
from strands.memory import MemoryManager
from strands_mem0 import Mem0MemoryStore

store = Mem0MemoryStore(user_id="alex", writable=True, extraction=True)
agent = Agent(memory_manager=MemoryManager(stores=[store]))
```

Set `MEM0_API_KEY` for the hosted platform, or pass `config=...` for a self-hosted Mem0 OSS backend.

## Local development

```bash
pip install hatch
hatch run test        # pytest (mocked client, no live server)
hatch run prepare     # format + lint + typecheck + test
```

## Release

Publish a GitHub release tagged `strands-mem0-v*` (e.g. `strands-mem0-v0.1.0`). The
release router (`.github/workflows/release.yml`) dispatches `strands-mem0-cd.yml`,
which builds the wheel and publishes it to PyPI via trusted publishing (OIDC).
