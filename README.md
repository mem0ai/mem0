# Mem0 Python SDK

<p align="center">
  <a href="https://github.com/mem0ai/mem0">
    <img src="docs/images/banner-sm.png" width="800px" alt="Mem0, the memory layer for personalized AI">
  </a>
</p>
<p align="center" style="display: flex; justify-content: center; gap: 20px; align-items: center;">
  <a href="https://trendshift.io/repositories/11194" target="blank">
    <img src="https://trendshift.io/api/badge/repositories/11194" alt="mem0ai%2Fmem0 | Trendshift" width="250" height="55"/>
  </a>
</p>

<p align="center">
  <a href="https://mem0.ai">Learn more</a>
  ·
  <a href="https://mem0.dev/DiG">Join Discord</a>
  ·
  <a href="https://mem0.dev/demo">Demo</a>
</p>

<p align="center">
  <a href="https://mem0.dev/DiG">
    <img src="https://img.shields.io/badge/Discord-%235865F2.svg?&logo=discord&logoColor=white" alt="Mem0 Discord">
  </a>
  <a href="https://pepy.tech/project/mem0ai">
    <img src="https://img.shields.io/pypi/dm/mem0ai" alt="Mem0 PyPI downloads">
  </a>
  <a href="https://github.com/mem0ai/mem0">
    <img src="https://img.shields.io/github/commit-activity/m/mem0ai/mem0?style=flat-square" alt="GitHub commit activity">
  </a>
  <a href="https://pypi.org/project/mem0ai" target="blank">
    <img src="https://img.shields.io/pypi/v/mem0ai?color=%2334D058&label=pypi%20package" alt="PyPI package version">
  </a>
  <a href="https://www.ycombinator.com/companies/mem0">
    <img src="https://img.shields.io/badge/Y%20Combinator-S24-orange?style=flat-square" alt="Y Combinator S24">
  </a>
</p>

Mem0 gives AI assistants and agents persistent memory. It extracts useful facts from conversations, scopes them to a user, agent, or run, and retrieves the relevant facts for later interactions. The Python package includes `MemoryClient` for the hosted Mem0 Platform and `Memory` for open-source, in-process memory.

## Requirements

- Python 3.10 or later
- Hosted Platform: `MEM0_API_KEY` from the [Mem0 dashboard](https://app.mem0.ai/dashboard/api-keys)
- Open source with the default providers: `OPENAI_API_KEY`

## Install

```bash
pip install mem0ai
```

For enhanced hybrid search with BM25 keyword matching and entity extraction:

```bash
pip install "mem0ai[nlp]"
python -m spacy download en_core_web_sm
```

## Platform or open source

| | Platform (`MemoryClient`) | Open source (`Memory`) |
|---|---|---|
| Import | `from mem0 import MemoryClient` | `from mem0 import Memory` |
| Where memories live | Mem0's hosted API | Your configured vector store |
| Required key | `MEM0_API_KEY` | `OPENAI_API_KEY` with the defaults, or keys for your chosen providers |
| Extraction | Managed and asynchronous | Runs synchronously against your configured LLM |
| Best for | Zero-ops production use | Local development and custom infrastructure |

## Platform quickstart

Set `MEM0_API_KEY`, then add a conversation:

```python
import os

from mem0 import MemoryClient

client = MemoryClient(api_key=os.environ["MEM0_API_KEY"])

messages = [
    {"role": "user", "content": "I am vegetarian and allergic to nuts."},
    {"role": "assistant", "content": "I will remember that."},
]
result = client.add(messages, user_id="alex")
print(result)
```

Hosted `add()` queues extraction and usually returns an `event_id` with `status: "PENDING"`. Do not search immediately after `add()`. Wait for processing to finish in the dashboard, or use a [`memory_add` webhook](https://docs.mem0.ai/platform/features/webhooks), then search:

```python
import os

from mem0 import MemoryClient

client = MemoryClient(api_key=os.environ["MEM0_API_KEY"])
results = client.search(
    "What does Alex eat?",
    filters={"user_id": "alex"},
    top_k=5,
)
print(results["results"])
```

`search()` and `get_all()` take entity IDs inside `filters`. `add()` and `delete_all()` take `user_id`, `agent_id`, or `run_id` as top-level keyword arguments.

## Open-source quickstart

Set `OPENAI_API_KEY` before using the default OpenAI LLM and embedder:

```python
from mem0 import Memory

memory = Memory()

messages = [
    {"role": "user", "content": "I am vegetarian and allergic to nuts."},
    {"role": "assistant", "content": "I will remember that."},
]
memory.add(messages, user_id="alex")

results = memory.search(
    "What does Alex eat?",
    filters={"user_id": "alex"},
    top_k=5,
)
print(results["results"])
```

The default `Memory` configuration uses OpenAI `gpt-5-mini`, OpenAI `text-embedding-3-small`, local Qdrant storage, and a SQLite history database. Pass a `MemoryConfig` or use `Memory.from_config()` to change the LLM, embedder, vector store, history path, or reranker.

## Configuration and features

| Feature | Documentation |
|---|---|
| Memory operations: `add`, `search`, `get`, `get_all`, `update`, `delete`, `delete_all`, `history` | [Python quickstart](https://docs.mem0.ai/open-source/python-quickstart) |
| Entity scoping with `user_id`, `agent_id`, and `run_id` | [Entity-scoped memory](https://docs.mem0.ai/platform/features/entity-scoped-memory) |
| Metadata and filters | [Metadata filtering](https://docs.mem0.ai/open-source/features/metadata-filtering) |
| Async clients: `AsyncMemory` and `AsyncMemoryClient` | [Async memory](https://docs.mem0.ai/open-source/features/async-memory) |
| LLMs, embedders, vector stores, and rerankers | [Components](https://docs.mem0.ai/components/llms/overview) |
| Graph memory | [Graph memory](https://docs.mem0.ai/platform/features/graph-memory) |
| Custom instructions | [Custom instructions](https://docs.mem0.ai/open-source/features/custom-instructions) |
| Multimodal input | [Multimodal support](https://docs.mem0.ai/open-source/features/multimodal-support) |
| Platform webhooks, export, feedback, expiration, and custom categories | [Platform features](https://docs.mem0.ai/platform/features) |

## Benchmarks

<p align="center">
  <a href="https://mem0.ai/research"><strong>Benchmarking Mem0's token-efficient memory algorithm</strong></a>
</p>

| Benchmark | Old | New | Tokens | Latency p50 |
|---|---:|---:|---:|---:|
| **LoCoMo** | 71.4 | **92.5** | 7.0K | 0.88s |
| **LongMemEval** | 67.8 | **94.4** | 6.8K | 1.09s |
| **BEAM (1M)** | n/a | **64.1** | 6.7K | 1.00s |
| **BEAM (10M)** | n/a | **48.6** | 6.9K | 1.05s |

All benchmarks use the same production-representative model stack, single-pass retrieval, and a top-200 retrieval budget. Scores reflect the managed Platform, which includes proprietary optimizations not available in the open-source SDK. Open-source results should show similar directional gains, but may not match these scores.

The current algorithm uses single-pass ADD-only extraction, first-class agent facts, entity linking, multi-signal retrieval, and temporal reasoning. Read the [research paper](https://mem0.ai/research), the [migration guide](https://docs.mem0.ai/migration/oss-v2-to-v3), or the open-source [evaluation framework](https://github.com/mem0ai/memory-benchmarks).

## Self-hosted server

Run Mem0 as a FastAPI service with PostgreSQL, pgvector, and Neo4j:

```bash
# Recommended: start the stack, create an admin, and issue the first API key.
cd server && make bootstrap

# Manual: start the stack, then finish setup in the browser wizard.
cd server && docker compose up -d
```

Self-hosted authentication is enabled by default. See the [self-hosted documentation](https://docs.mem0.ai/open-source/overview) and [upgrade notes](https://docs.mem0.ai/open-source/setup#upgrade-notes).

## CLI

Manage hosted memories from your terminal:

```bash
pip install mem0-cli

mem0 init
mem0 add "Prefers dark mode and vim keybindings" --user-id alice
mem0 search "What does Alice prefer?" --user-id alice
```

AI agents can create an account without email or a dashboard:

```bash
mem0 init --agent --agent-caller claude-code
```

The human owner can claim the account later with `mem0 init --email <their-email>`. The API key and memories remain unchanged. See the [CLI documentation](https://docs.mem0.ai/platform/cli) and [agent signup guide](https://docs.mem0.ai/platform/agent-signup).

## Agent skills

Install reference skills to give compatible coding assistants Mem0 context:

```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0
npx skills add https://github.com/mem0ai/mem0 --skill mem0-cli
```

Install pipeline skills for end-to-end workflows:

```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0-integrate
npx skills add https://github.com/mem0ai/mem0 --skill mem0-test-integration
npx skills add https://github.com/mem0ai/mem0 --skill mem0-oss-to-platform
```

See the [skills catalog](./skills/) or [Vibecoding with Mem0](https://docs.mem0.ai/vibecoding).

## Integrations and demos

- [ChatGPT with Memory demo](https://mem0.dev/demo)
- [Browser extension](https://chromewebstore.google.com/detail/onihkkbipkfeijkadecaafbgagkhglop?utm_source=item-share-cb)
- [LangGraph integration](https://docs.mem0.ai/integrations/langgraph)
- [CrewAI integration](https://docs.mem0.ai/integrations/crewai)

## Documentation and help

- [Python quickstart](https://docs.mem0.ai/open-source/python-quickstart)
- [Platform quickstart](https://docs.mem0.ai/platform/quickstart)
- [API reference](https://docs.mem0.ai/api-reference)
- [Discord](https://mem0.dev/DiG)
- [GitHub issues](https://github.com/mem0ai/mem0/issues)
- Email: founders@mem0.ai

## Contributing

Read [CONTRIBUTING.md](./CONTRIBUTING.md) before opening an issue or pull request.

## Citation

```bibtex
@article{mem0,
  title={Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory},
  author={Chhikara, Prateek and Khant, Dev and Aryan, Saket and Singh, Taranjeet and Yadav, Deshraj},
  journal={arXiv preprint arXiv:2504.19413},
  year={2025}
}
```

## License

Apache 2.0. See [LICENSE](./LICENSE).
