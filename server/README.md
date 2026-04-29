# Mem0 Self-Hosted Server

Mem0 ships a self-hosted FastAPI server plus a local dashboard. It is secure by default, supports dashboard login and API keys, and exposes OpenAPI docs at `/docs`.

## Quick Start

### Agent-first

Run one command; the terminal prints the admin email, password, and first API key.

```bash
cd server
make bootstrap
```

This starts the stack, waits for the API and dashboard to be ready, creates the first admin, and generates the first API key.

> The generated credentials print once in the `=== Ready ===` block. Save the password and API key before closing the terminal — the API key cannot be recovered afterwards.

> `make bootstrap` skips the setup wizard, so the use-case → custom-instructions step doesn't run. To add custom instructions afterwards, `POST /configure` with `{"custom_instructions": "..."}`, or run the Browser-first flow on a fresh install.

You can override the generated credentials:

```bash
cd server
make bootstrap EMAIL=admin@company.com PASSWORD='strong-password' NAME='Admin'
```

For machine-readable output:

```bash
cd server
OUTPUT=json make seed
```

Teardown:

```bash
# Stop the stack
cd server && make down

# Wipe all data (including the Postgres volume)
cd server && make clean
```

### Browser-first

Start the stack and finish setup by walking through the wizard in your browser.

```bash
cd server
make up
```

Then open `http://localhost:3000` and complete the setup wizard.

## Security Defaults

- Dashboard login uses JWTs.
- Programmatic access uses `X-API-Key`.
- Auth is enabled by default.
- `AUTH_DISABLED=true` exists for local development only and should not be used in production.

## Forgotten password

Reset an admin password from the host while the stack is running:

```bash
cd server
make reset-admin-password EMAIL=admin@example.com PASSWORD='new-strong-password'
```

This is the supported recovery path. Anyone with shell access to the host already has full access to the database and secrets, so this command does not expand the attack surface.

## Request log retention

The `request_logs` table is append-only and grows with traffic (~864k rows/day at 10 req/s). Prune it periodically:

```bash
cd server
make prune-logs                               # defaults to 30 days
make prune-logs REQUEST_LOG_RETENTION_DAYS=7  # shorter window
```

Wire the command into cron or a systemd timer in production. The `created_at` column uses a BRIN index, so range deletes stay cheap even on large tables.

## Local URLs

- Dashboard: `http://localhost:3000`
- API: `http://localhost:8888`
- OpenAPI docs: `http://localhost:8888/docs`

## Dashboard

Once logged in, the dashboard exposes:

- **Requests** — live audit log of API calls (method, path, status, latency).
- **Memories** — browse memories, filter by user ID.
- **Entities** — list every `user_id`, `agent_id`, and `run_id` that owns memories, with counts. Delete an entity to cascade-delete its memories.
- **API Keys** — create, label, and revoke per-user keys.
- **Configuration** — runtime LLM and embedder override. Changes persist to the app database and reapply on restart, layered over the values from your `.env`.
- **Settings** — account profile and password.

## Configuration

### LLM and Embedder Providers

The server bundles several LLM and embedder providers. Set these environment variables in `.env` to choose which ones to use:

| Variable | Default | Description |
|---|---|---|
| `MEM0_DEFAULT_LLM_PROVIDER` | `openai` | LLM provider (see bundled list below) |
| `MEM0_DEFAULT_LLM_MODEL` | `gpt-4.1-nano-2025-04-14` | Model name for the chosen LLM provider |
| `MEM0_DEFAULT_EMBEDDER_PROVIDER` | `openai` | Embedder provider (see bundled list below) |
| `MEM0_DEFAULT_EMBEDDER_MODEL` | `text-embedding-3-small` | Model name for the chosen embedder |

**Bundled LLM providers:** `openai`, `anthropic`, `gemini`, `minimax`, `deepseek`, `lmstudio`

**Bundled embedder providers:** `openai`, `gemini`, `lmstudio`

Each provider class reads its own API key and base URL from the environment — the server only passes the provider name and model. Set only the variables your chosen provider needs:

| Provider | Required env vars | Optional env vars |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `OPENAI_BASE_URL` |
| Anthropic | `ANTHROPIC_API_KEY` | — |
| Gemini | `GOOGLE_API_KEY` | — |
| MiniMax | `MINIMAX_API_KEY` | `MINIMAX_API_BASE` |
| DeepSeek | `DEEPSEEK_API_KEY` | `DEEPSEEK_API_BASE` |
| LM Studio | (none) | `LMSTUDIO_BASE_URL` (default: `http://localhost:1234/v1`) |

**Example: MiniMax LLM + local LM Studio embedding**

```bash
MEM0_DEFAULT_LLM_PROVIDER=minimax
MEM0_DEFAULT_LLM_MODEL=MiniMax-M2.7
MINIMAX_API_KEY=sk-cp-xxx
MINIMAX_API_BASE=https://api.minimaxi.com/anthropic

MEM0_DEFAULT_EMBEDDER_PROVIDER=lmstudio
MEM0_DEFAULT_EMBEDDER_MODEL=nomic-ai/nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf
LMSTUDIO_BASE_URL=http://localhost:1234/v1
```

**Example: DeepSeek LLM**

```bash
MEM0_DEFAULT_LLM_PROVIDER=deepseek
MEM0_DEFAULT_LLM_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-xxx
```

### Runtime Reconfiguration

The `POST /configure` endpoint (available in the dashboard) allows changing the LLM and embedder at runtime. Changes persist to the app database and reapply on restart, layered over `.env` defaults. Only bundled providers are accepted.

### Adding a New Provider

1. Add the provider's package to `requirements.txt` if it has one (most OpenAI-compatible providers need no extra dependency).
2. Add the provider name to `BUNDLED_LLM_PROVIDERS` or `BUNDLED_EMBEDDER_PROVIDERS` in `server/main.py`.
3. Set `MEM0_DEFAULT_LLM_PROVIDER` (or `_EMBEDDER_PROVIDER`) and the provider's own environment variables in `.env`.

The provider class in `mem0/` handles its own configuration — no server code changes are needed beyond the allowlist.

## Telemetry

Enabled by default, matching the Mem0 OSS library. Sends at most two events per install to the same anonymous PostHog project the library uses:

- `admin_registered` — fired when the first admin is created (wizard or direct API call). Properties: email domain, server version, install UUID.
- `onboarding_completed` — fired when the setup wizard reaches its final success state. Carries the same properties plus the freeform `use_case` the operator entered. API-only bootstraps never emit this event.

Set `MEM0_TELEMETRY=false` to opt out.

## Security headers

The dashboard sets the following response headers on every path (see `server/dashboard/next.config.mjs`):

- `X-Frame-Options: DENY`
- `Content-Security-Policy: frame-ancestors 'none'`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`

Together these prevent iframe embedding, sniffing of mislabelled MIME types, and cross-origin referrer leaks. Harden further behind your own reverse proxy if needed.

## Reference

Additional product and API documentation lives at [docs.mem0.ai](https://docs.mem0.ai/open-source/overview).
