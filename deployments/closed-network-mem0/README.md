# Closed-Network Mem0 Self-Host

This folder runs Mem0 self-hosted without `api.mem0.ai`.

- Mem0 API and dashboard run locally.
- Chat LLM calls your internal OpenAI-compatible API from `~/.openapi`.
- Embeddings use a small local Ollama model, default `nomic-embed-text`.
- Memory vectors are stored in the bundled Postgres + pgvector service.

## Get Started

1. Put your internal OpenAI-compatible token in `~/.openapi`.
2. Start the self-host stack from this folder.
3. Run the smoke test.
4. Export the generated self-host Mem0 API key for OpenCode.

```bash
cd deployments/closed-network-mem0
./scripts/bootstrap.sh
./scripts/smoke-test.sh

export MEM0_SELF_HOST=true
export MEM0_BASE_URL=http://localhost:8888
export MEM0_API_KEY="$(cat .mem0-api-key)"
opencode plugin @mem0/opencode-plugin
```

Restart OpenCode after exporting the variables. The plugin will use the
self-host REST API instead of `api.mem0.ai`.

## Required `~/.openapi`

Create `~/.openapi` with the internal API token. A raw one-line token is
accepted:

```bash
<internal-token>
```

If you prefer env-file style, this also works:

```bash
OPENAI_API_KEY=<internal-token>
OPENAI_BASE_URL=https://<internal-openai-compatible-api>/v1
MEM0_DEFAULT_LLM_MODEL=<chat-model-name>
```

When `~/.openapi` is a raw token, set the endpoint and model in this folder's
`.env`:

```bash
OPENAI_BASE_URL=https://<internal-openai-compatible-api>/v1
MEM0_DEFAULT_LLM_MODEL=<chat-model-name>
```

If `.env` does not exist yet, run `./scripts/bootstrap.sh` once to create it,
fill these two values, then run `./scripts/bootstrap.sh` again.

The name is intentionally `~/.openapi` to match the local convention. Do not
commit this file.

## Start the Self-Host Stack

```bash
cd deployments/closed-network-mem0
./scripts/bootstrap.sh
```

The script creates `.env` if needed, starts Docker Compose, creates the first
admin, issues a self-host API key, and applies this runtime config:

```json
{
  "vector_store": {
    "provider": "pgvector",
    "config": {
      "embedding_model_dims": 768
    }
  },
  "llm": {
    "provider": "openai",
    "config": {
      "api_key": "from ~/.openapi",
      "openai_base_url": "from ~/.openapi",
      "model": "from ~/.openapi"
    }
  },
  "embedder": {
    "provider": "ollama",
    "config": {
      "model": "nomic-embed-text",
      "ollama_base_url": "http://ollama:11434",
      "embedding_dims": 768
    }
  }
}
```

The script normalizes `~/.openapi` into `.openapi.env` for Docker Compose. The
generated self-host API key is written to `.mem0-api-key`.

Do not commit `.openapi.env`, `.env`, or `.mem0-api-key`; they are ignored by
this folder's `.gitignore`.

## Verify

```bash
./scripts/smoke-test.sh
```

Or call the REST API directly:

```bash
API_KEY="$(cat .mem0-api-key)"
curl -X POST http://localhost:8888/memories \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"I use local embeddings."}],"user_id":"demo"}'
```

## Configure

Edit `.env` before running `bootstrap.sh` if you need different ports or a
different embedding model:

```bash
API_PORT=8888
DASHBOARD_PORT=3000
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
MEM0_DEFAULT_EMBEDDER_DIMS=768
```

If you change the embedding model or dimensions after data exists, reset the
Postgres volume first. pgvector collections are dimension-sensitive.

```bash
docker compose down -v
./scripts/bootstrap.sh
```

## OpenCode Integration

The OpenCode plugin can use this self-host server when these variables are set
in the shell that launches OpenCode:

```bash
export MEM0_SELF_HOST=true
export MEM0_BASE_URL=http://localhost:8888
export MEM0_API_KEY="$(cat deployments/closed-network-mem0/.mem0-api-key)"
```

Then install or restart the plugin:

```bash
opencode plugin @mem0/opencode-plugin
```

In self-host mode, the plugin stores `app_id` as memory metadata so project
scoping still works. Hosted-only features such as project category management
and async event status are skipped or reported as unsupported by the self-host
REST API.

## Closed-Network Notes

This compose file is closed-network oriented, but first-time Docker builds still
need local access to required images and Python/Node packages unless your
environment provides an internal registry/cache.

Mirror or pre-load these dependencies for a fully disconnected network:

- `python:3.12-slim`
- `pgvector/pgvector:pg17`
- `node:20-alpine`
- `ollama/ollama:latest`
- Python packages from `server/requirements.txt`
- Dashboard packages from `server/dashboard/pnpm-lock.yaml`
- The Ollama embedding model, default `nomic-embed-text`

After the images and Ollama model are present locally, normal runtime traffic is
limited to:

- Mem0 API to Postgres
- Mem0 API to Ollama for embeddings
- Mem0 API to your internal OpenAI-compatible chat endpoint

## Why Not The Existing `mem0` CLI?

The installed `mem0` CLI targets hosted Platform API paths such as
`/v3/memories/add/` and `/v1/memories/...`. The self-host server exposes OSS REST
paths such as `/memories` and `/search`, so this setup uses direct REST calls or
a small internal wrapper instead of the hosted CLI.
