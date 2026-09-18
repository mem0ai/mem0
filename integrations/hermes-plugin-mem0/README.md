# Mem0 Memory Provider

Standalone copy of the [Nous Research provider](https://github.com/NousResearch/hermes-plugin-mem0/tree/3fc36950b2b7c19cdd81c6de99f10d2cbed850af), maintained in this subdirectory. The original MIT license is retained.

Server-side LLM fact extraction with semantic search and hybrid multi-signal retrieval via the Mem0 Platform v3 API.

## Requirements

- `pip install mem0ai`
- Mem0 API key from [app.mem0.ai](https://app.mem0.ai)

## Install

After this directory is merged to Mem0's main branch:

```bash
hermes plugins install mem0ai/mem0/integrations/hermes-plugin-mem0
hermes plugins enable mem0
```

Hermes versions that still bundle Mem0 prefer the bundled provider. The external copy
loads once that bundled provider is removed. Keep `memory.provider: mem0`, your existing
`mem0.json`, `MEM0_*` variables, user ID, and OSS storage paths.

Automatic migration requires Hermes' migration support and an approved catalog entry
named `mem0`, with `repo: https://github.com/mem0ai/mem0`,
`subdir: integrations/hermes-plugin-mem0`, and a full reviewed commit SHA.
Merging this directory does not register that catalog entry. Startup installation also
requires `security.allow_lazy_installs`; disabled or offline installs require manual action.

The plugin provides `get_config_schema`, `save_config`, and `post_setup` for CLI setup.
It does not ship a Desktop `config_schema.py` panel or provider-specific `cli.py` commands.
On Hermes v0.21.3, install the dependencies declared in `pyproject.toml` into the Hermes
Python environment explicitly; newer Hermes installers handle them automatically.

## Setup

```bash
hermes memory setup    # select "mem0"
```

Or manually:
```bash
hermes config set memory.provider mem0
echo "MEM0_API_KEY=your-key" >> ~/.hermes/.env
```

## Config

Behavioral settings live in `$HERMES_HOME/mem0.json` (set them via `hermes memory setup`). Only the secret `MEM0_API_KEY` belongs in `~/.hermes/.env`.

| Key | Default | Description |
|-----|---------|-------------|
| `mode` | `platform` | `platform` (Mem0 Cloud) or `oss` (self-managed, in-process) |
| `host` | — | Self-hosted Mem0 server URL (the Docker dashboard). When set, connects over HTTP with `X-API-Key`. Don't combine with `mode: oss` |
| `user_id` | `hermes-user` | User identifier on Mem0 |
| `agent_id` | `hermes` | Agent identifier |
| `rerank` | `false` | Rerank search results for relevance (platform mode only) |
| `sync_max_chars` | `450` | Per-message character cap applied before each turn is sent for fact extraction (cut at the last sentence boundary). Default fits 512-token embedders; raise it (e.g. `6000`) for 8k-token embedders such as `text-embedding-3-small`, `jina-embeddings-v3`, `bge-m3` |

The plugin has three connection modes:

- **Platform** — Mem0's hosted cloud (`api.mem0.ai`). Set `MEM0_API_KEY`. (default)
- **Self-hosted dashboard** — a Mem0 server you run yourself via Docker. Set `host`. See below.
- **OSS** — run Mem0 in-process with your own LLM + vector store. Set `mode: oss`. See below.

## Self-Hosted Dashboard (Server) Mode

Connect the plugin to a standalone Mem0 server you run yourself — the Docker-shipped Mem0 dashboard/server with its own REST API. Unlike OSS mode (which runs `mem0ai` in-process with your own vector store), here the plugin just talks HTTP to your server.

1. Run the Mem0 server (FastAPI + pgvector) from its Docker image and note its URL and `ADMIN_API_KEY`.
2. Point the plugin at it — via the setup wizard:
   ```bash
   hermes memory setup    # select "mem0" → "Self-hosted server"
   # Or non-interactive:
   hermes memory setup mem0 --mode selfhosted --host http://localhost:8888 --api-key your-admin-api-key
   ```
   or via env vars:
   ```bash
   echo "MEM0_HOST=http://localhost:8888" >> ~/.hermes/.env
   echo "MEM0_API_KEY=your-admin-api-key" >> ~/.hermes/.env
   ```
   or in `$HERMES_HOME/mem0.json`:
   ```json
   {
     "host": "http://localhost:8888",
     "api_key": "your-admin-api-key"
   }
   ```
3. Start a fresh Hermes session and call `mem0_search` — it connects to your server.

The plugin authenticates with `X-API-Key` and uses the server's `/search` and `/memories` routes. `api_key` is optional — omit it only for servers running with `AUTH_DISABLED`.

> Setting `host` routes to the self-hosted server automatically. Don't set `mode: oss` — OSS takes precedence and ignores `host`.

## OSS (Self-Hosted) Mode

Run Mem0 locally with your own LLM, embedder, and vector store. This is the in-process SDK mode. To instead connect to a Mem0 server you run via Docker, see [Self-Hosted Dashboard (Server) Mode](#self-hosted-dashboard-server-mode) above.

### Interactive Setup

```bash
hermes memory setup
# Select "mem0" → "Open Source (self-hosted)"
# Follow prompts for LLM, embedder, and vector store
```

### Agent-Driven Setup (Flags)

```bash
hermes memory setup mem0 --mode oss \
  --oss-llm openai --oss-llm-key sk-... \
  --oss-vector qdrant
```

### Supported Providers

| Component | Providers |
|-----------|-----------|
| LLM | openai, ollama |
| Embedder | openai, ollama |
| Vector Store | qdrant (local/server), pgvector |

### Flags Reference

| Flag | Description |
|------|-------------|
| `--mode` | `platform`, `selfhosted`, or `oss` |
| `--oss-llm` | LLM provider (default: openai) |
| `--oss-llm-key` | LLM API key |
| `--oss-embedder` | Embedder provider (default: openai) |
| `--oss-vector` | Vector store (default: qdrant) |
| `--oss-vector-path` | Qdrant local path |
| `--user-id` | User identifier |

## Switching Modes

### Platform to OSS

```bash
hermes memory setup mem0 --mode oss --oss-llm-key sk-...
```

Or edit `$HERMES_HOME/mem0.json` directly:
```json
{
  "mode": "oss",
  "oss": {
    "llm": {"provider": "openai", "config": {"model": "gpt-5-mini", "is_reasoning_model": true}},
    "embedder": {"provider": "openai", "config": {"model": "text-embedding-3-small"}},
    "vector_store": {"provider": "qdrant", "config": {"path": "~/.hermes/mem0_qdrant"}}
  }
}
```

### OSS to Platform

```bash
hermes memory setup mem0 --mode platform --api-key sk-...
```

### Dry Run (preview without writing)

```bash
hermes memory setup mem0 --mode oss --oss-llm-key sk-... --dry-run
```

## Tools

| Tool | Description |
|------|-------------|
| `mem0_search` | Semantic search by meaning |
| `mem0_add` | Store a fact verbatim (no LLM extraction) |
| `mem0_update` | Update a memory's text by ID |
| `mem0_delete` | Delete a memory by ID |

## Troubleshooting

### "Mem0 temporarily unavailable"

Circuit breaker tripped after 5 consecutive failures. Resets after 2 minutes.

- **Platform mode**: Check API key and internet connectivity.
- **OSS mode**: Check that your vector store (qdrant/pgvector) is running.

### OSS: Qdrant connection refused

```bash
# If using local Qdrant, check the storage path is writable:
ls -la ~/.hermes/mem0_qdrant

# If using Qdrant server, check it's reachable:
curl http://localhost:6333/healthz
```

### OSS: PGVector connection refused

```bash
# Verify PostgreSQL is running and accepting connections:
pg_isready -h localhost -p 5432
```

### OSS: Ollama not reachable

```bash
# Check Ollama is running:
curl http://localhost:11434/api/tags
```

### Memories not appearing

- `mem0_add` stores verbatim (no extraction). Use `sync_turn` for LLM extraction.
- Search uses semantic matching — try broader queries.
- Check `user_id` matches between sessions (`$HERMES_HOME/mem0.json`).

### Existing OSS collection has different embedding dimensions

Initialization now fails without deleting the existing collection. Restore the previous
embedding model/dimensions or select a new collection name and migrate data explicitly.
Setup saves credentials and OSS configuration atomically with owner-only permissions.

## Local checks

From the Mem0 repository root, with `pytest` installed:

```bash
python -m pytest -q --confcutdir=integrations/hermes-plugin-mem0/tests integrations/hermes-plugin-mem0/tests
ruff check integrations/hermes-plugin-mem0
isort --check-only --profile black integrations/hermes-plugin-mem0
```

For the runtime smoke, use an environment containing Hermes dependencies, `mem0ai`, and
`qdrant-client`:

```bash
HERMES_SOURCE=/path/to/hermes-agent python integrations/hermes-plugin-mem0/tests/smoke_hermes.py
```

The smoke uses the real Hermes external loader, Mem0 SDK, and an on-disk Qdrant database
in a temporary profile. It exercises CLI setup/status, all four tools, recall, background extraction,
existing user identity, private files, dimension-mismatch protection, shutdown, and persistence across restart. Only the OpenAI-compatible
model service is simulated locally; this does not test live cloud credentials or model quality.
