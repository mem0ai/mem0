# Python SDK (`mem0/`)

The `mem0ai` package on PyPI. Memory core plus five pluggable provider categories.

## Commands

```bash
hatch shell dev_py_3_11   # or dev_py_3_9 / dev_py_3_10 / dev_py_3_12
pre-commit install        # first time only; runs ruff + isort on commit

make lint                 # ruff check
make format               # ruff format
make sort                 # isort mem0/
make test                 # pytest tests/
make test-py-3.9          # pin a Python version (3.9 through 3.12)
make install_all          # optional deps; run before the full test suite
make build                # hatch build
```

Use `hatch` for environments and dependencies. Do not use `pip` or `conda`.

## Conventions

- **Python 3.9 through 3.12.** Code must run on 3.9.
- **Ruff**, line length **120**. `cli/python/` uses 100; do not carry that config across.
- **isort**, `profile = "black"`, first-party `mem0` and `mem0_cli`.
- **Pydantic v2** for every data model and config class.
- **pytest** with pytest-mock and pytest-asyncio. Tests live in `../tests/`.
- Source files are `snake_case.py`.

## Layout

```
mem0/
├── memory/          Memory, AsyncMemory
├── client/          MemoryClient, AsyncMemoryClient
├── configs/         MemoryConfig and per-category config models
├── llms/            24 providers
├── embeddings/      15 providers
├── vector_stores/   30 providers
├── graphs/          4 providers
└── reranker/        5 providers
```

## Provider pattern

Every category follows the same shape: a `base.py` with the abstract class, one module per provider, config models in `configs.py`, registration in `__init__.py`.

| Category | Count | Examples |
|----------|-------|---------|
| LLMs | 24 | OpenAI, Anthropic, AWS Bedrock, Azure OpenAI, Gemini, Groq, Ollama, Together, DeepSeek, vLLM, LiteLLM, LM Studio, xAI |
| Vector stores | 30 | Qdrant, Pinecone, Chroma, Weaviate, Milvus, MongoDB, Redis, Elasticsearch, pgvector, Supabase, Faiss, S3 Vectors |
| Embeddings | 15 | OpenAI, Azure OpenAI, Gemini, HuggingFace, FastEmbed, Together, AWS Bedrock, Ollama, Vertex AI |
| Graph stores | 4 | Neo4j, Memgraph, Kuzu, Apache AGE |
| Rerankers | 5 | Cohere, HuggingFace, LLM-based, Sentence Transformer, Zero Entropy |

### Adding a provider

1. Create `mem0/<category>/<provider_name>.py`.
2. Inherit the abstract base class from `mem0/<category>/base.py`.
3. Add its config to `mem0/<category>/configs.py` if the category uses one.
4. Register it in `mem0/<category>/__init__.py`.
5. Add tests under `tests/<category>/<provider_name>/`.
6. Put new dependencies in an **optional** group in `pyproject.toml`, never in core `dependencies`.
7. Match an existing provider in the same category exactly: method signatures, error handling, config structure.
8. Add an integration guide under `docs/integrations/`.

## Public API

| Class | Purpose | Import |
|-------|---------|--------|
| `Memory` | Self-hosted, sync | `from mem0 import Memory` |
| `AsyncMemory` | Self-hosted, async | `from mem0 import AsyncMemory` |
| `MemoryClient` | Hosted platform, sync | `from mem0 import MemoryClient` |
| `AsyncMemoryClient` | Hosted platform, async | `from mem0 import AsyncMemoryClient` |

Both `Memory` and `MemoryClient` expose the same surface:

| Method | Purpose |
|--------|---------|
| `add(messages, *, user_id, agent_id, run_id, metadata)` | Store a memory |
| `search(query, *, user_id, agent_id, run_id, limit, filters)` | Search memories |
| `get(memory_id)` | Fetch one memory |
| `get_all(*, user_id, agent_id, run_id, limit)` | List memories |
| `update(memory_id, data)` | Update a memory |
| `delete(memory_id)` | Delete a memory |
| `delete_all(*, user_id, agent_id, run_id)` | Delete a scope |
| `history(memory_id)` | Change history for a memory |

Changing any of these signatures means updating `docs/` in the same PR.

### Import paths

| What | Import |
|------|--------|
| Memory classes | `from mem0 import Memory, AsyncMemory` |
| Platform client | `from mem0 import MemoryClient, AsyncMemoryClient` |
| Configuration | `from mem0.configs.base import MemoryConfig` |
| LLM provider | `from mem0.llms.<provider> import <ProviderLLM>` |
| Embedding provider | `from mem0.embeddings.<provider> import <ProviderEmbedding>` |
| Vector store provider | `from mem0.vector_stores.<provider> import <ProviderVectorStore>` |

## Graph memory

An optional layer on top of vector memory for relationship-aware retrieval, configured through the `graph` section of `MemoryConfig`. It supplements vector search rather than replacing it.
