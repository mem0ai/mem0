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

> These are localhost defaults. For LAN access, set `DASHBOARD_URL` and `NEXT_PUBLIC_API_URL` to your machine's LAN IP in `.env`.

### LAN / Network Deployment

The stack supports serving LAN clients out of the box. Set these environment variables in your `.env` file:

```env
DASHBOARD_URL=http://YOUR_LAN_IP:3000
NEXT_PUBLIC_API_URL=http://YOUR_LAN_IP:8888
INSTANCE_NAME=Mem0
EXTRA_CORS_ORIGINS=
```

**CORS behavior:**
- When `AUTH_DISABLED=true` (local dev), CORS allows all origins (`*`) — any LAN client can call the API without origin configuration.
- When auth is enabled, CORS allows `DASHBOARD_URL` plus any origins listed in `EXTRA_CORS_ORIGINS` (comma-separated).
- Use `EXTRA_CORS_ORIGINS` to whitelist additional frontend apps or tools running on other LAN machines.

**PostgreSQL access:**
- By default, the Postgres port (8432) is bound to `127.0.0.1` (localhost only) for security.
- To expose Postgres to the LAN, change the port mapping in `docker-compose.yaml` from `127.0.0.1:8432:5432` to `8432:5432`.

**Local source install:**
- The API container installs from the local `mem0/` source directory (`/opt/mem0-src`) instead of PyPI, so code changes are picked up on container rebuild without publishing a package.

### Transient Error Retry

The API automatically retries transient upstream errors (provider timeouts, rate limits, service unavailable) on the following endpoints:

- `POST /memories`
- `POST /search`

Retry settings:
- **Attempts:** 3
- **Backoff:** Linear (1s × attempt number)
- **Transient codes:** `provider_timeout`, `provider_rate_limited`, `provider_unavailable`, `datastore_unavailable`, `vector_store_unavailable`, `provider_bad_request`

Client errors (400/401/403/404/422) are never retried.

## Dashboard

Once logged in, the dashboard exposes:

- **Requests** — live audit log of API calls (method, path, status, latency).
- **Memories** — browse memories, filter by user ID.
- **Entities** — list every `user_id`, `agent_id`, and `run_id` that owns memories, with counts. Delete an entity to cascade-delete its memories.
- **API Keys** — create, label, and revoke per-user keys.
- **Configuration** — runtime LLM and embedder override. Changes persist to the app database and reapply on restart, layered over the values from your `.env`.
- **Settings** — account profile and password.

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

## API Notes

- `POST /search` with no `filters` field (or empty filters) searches across all users.
- `DELETE /memories/{id}` returns 404 for invalid or not-found memory IDs.

## Reference

Additional product and API documentation lives at [docs.mem0.ai](https://docs.mem0.ai/open-source/overview).
