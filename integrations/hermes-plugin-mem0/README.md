# Mem0 for Hermes Agent

Native Hermes memory provider, version **1.4.0**, based on the Nous Research
[1.3.0 handoff](https://github.com/NousResearch/hermes-plugin-mem0/tree/3fc36950b2b7c19cdd81c6de99f10d2cbed850af).
Keeps platform, self-hosted HTTP, and in-process OSS modes and all four existing tools.
See [HANDOFF.md](HANDOFF.md) for provenance and compatibility details.

## Install and activate

Requires Python 3.11+ and the Hermes memory-provider API present in **v0.21.3
(v2026.9.14)**. Prefer the latest Hermes release. Earlier Hermes versions have not
been validated. Install dependencies into the Python environment that runs Hermes:

```bash
# Replace this with your Hermes checkout path.
HERMES_REPO=/path/to/hermes-agent
uv pip install --python "$HERMES_REPO/.venv/bin/python" 'mem0ai>=2.0.10,<3' 'httpx>=0.27,<1'
```

Recent Hermes development versions install `pyproject.toml` dependencies automatically;
v0.21.3 needs the explicit command above. Optional OSS providers can require additional
packages installed by the setup wizard.

### Local worktree preview

From the Mem0 worktree root, copy the complete directory to the active Hermes profile.
This command refuses to overwrite an existing user plugin:

```bash
python3 - <<'PYINSTALL'
import os
import shutil
from pathlib import Path

home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
shutil.copytree("integrations/hermes-plugin-mem0", home / "plugins" / "mem0")
PYINSTALL
```

**Installing is not enough on Hermes versions that bundle Mem0.** Both v0.21.3 and
Hermes main checked on September 18, 2026 still contain `plugins/memory/mem0`.
Hermes always selects that bundled provider ahead of a same-named user plugin;
`hermes plugins enable mem0` does not change this precedence.

To preview this version without changing your normal Hermes checkout, make a separate
Hermes worktree and replace its bundled copy. From the Mem0 worktree root:

```bash
MEM0_WORKTREE="$PWD"
HERMES_PREVIEW="${TMPDIR:-/tmp}/hermes-mem0-preview"
git -C "$HERMES_REPO" worktree add --detach "$HERMES_PREVIEW" HEAD
mv "$HERMES_PREVIEW/plugins/memory/mem0" "$HERMES_PREVIEW/.mem0-bundled-backup"
cp -R "$MEM0_WORKTREE/integrations/hermes-plugin-mem0" "$HERMES_PREVIEW/plugins/memory/mem0"
cd "$HERMES_PREVIEW"
"$HERMES_REPO/.venv/bin/python" -m hermes_cli.main memory setup
"$HERMES_REPO/.venv/bin/python" -m hermes_cli.main chat
```

Use a fresh `HERMES_HOME` for a separate test profile, or your existing profile to retain
its configuration and memory identity. The preview uses your existing Hermes environment;
the original provider remains in the normal checkout and in the preview backup.
Updating Hermes can restore its bundled copy, so recheck which provider is selected.
Once Hermes no longer bundles Mem0, the user plugin copy loads directly.

### After this integration is published

Only after `integrations/hermes-plugin-mem0` is available on the remote branch:

```bash
hermes plugins install mem0ai/mem0/integrations/hermes-plugin-mem0
hermes plugins enable mem0
hermes memory setup
hermes memory status
```

The bundled-provider precedence above still applies. This remote command does not install
unpublished worktree changes. Keep the name `mem0`, existing `mem0.json`, `MEM0_*` variables,
and `memory.provider: mem0`; no memory migration or new user ID is required.

## Capture and recall

Automatic capture processes the completed user/assistant turn with plugin-local
message preparation: known-secret redaction and token-aware batching. Empty text is skipped.
It preserves full completed-turn text after redaction instead of dropping everything after 450 characters.
Raw tool results and the full historical transcript are not captured. Platform mode sends
prepared turn text to Mem0 Cloud for extraction; HTTP and OSS modes use their configured
server or model providers. Pattern-based redaction cannot recognize every possible secret.

An explicit positive `sync_max_chars` still limits each message chunk; long messages are
split across chunks without losing their remaining text. The default is no character cap
for platform/HTTP and 450 characters per chunk for OSS. Batches also obey the token
budget. Writes attach the Hermes session as Mem0’s top-level `run_id`. Recall does not filter by
`run_id`, so the existing user identity continues to recall across sessions. Automatic
capture uses an in-memory queue: process crashes can lose queued turns, and failed backend
batches are logged without durable retries. Shutdown drains the queue for a bounded time;
a stuck backend can leave queued turns unfinished.

This directory owns its provider lifecycle, setup, tools, SDK backends, and
`_message_utils.py`. It is self-contained; no shared runtime or build step is required.

## Config

Behavioral settings live in `$HERMES_HOME/mem0.json` (set them via `hermes memory setup`). Store credentials in the active profile’s `$HERMES_HOME/.env`.

| Key | Default | Description |
|-----|---------|-------------|
| `mode` | `platform` | `platform` (Mem0 Cloud) or `oss` (self-managed, in-process) |
| `host` | — | Self-hosted Mem0 server URL (the Docker dashboard). When set, connects over HTTP with `X-API-Key`. Don't combine with `mode: oss` |
| `user_id` | Gateway user ID, else `hermes-user` | Explicit config or `MEM0_USER_ID` preserves the same identity across hosts. The legacy `hermes-user` placeholder permits gateway fallback. |
| `agent_id` | `hermes` | Agent identifier |
| `rerank` | `false` | Rerank search results for relevance (platform mode only) |
| `sync_max_chars` | Uncapped (platform/HTTP), `450` (OSS) | Positive character limit per chunk; longer text is split, not discarded. Increase for larger OSS embedding windows. |

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
| `mem0_add` | Store an explicit fact after known-secret redaction (no LLM extraction) |
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

- `mem0_add` stores a redacted fact without extraction. Completed turns are extracted automatically.
- Search uses semantic matching — try broader queries.
- Check `user_id` matches between sessions (`$HERMES_HOME/mem0.json`).

### Existing OSS collection has different embedding dimensions

Initialization fails with a configuration error instead of deleting or recreating the
collection. Restore the original embedding model/dimensions, or explicitly configure a new
collection name. Existing vectors remain untouched.

## Development

Run the offline checks from the Mem0 repository root (requires `pytest` and `httpx`):

```bash
python -m pytest -q --confcutdir=integrations/hermes-plugin-mem0/tests integrations/hermes-plugin-mem0/tests
ruff check integrations/hermes-plugin-mem0
isort --check-only --profile black integrations/hermes-plugin-mem0
```

The `--confcutdir` option keeps pytest from importing the Hermes entry point before
the tests install their host stubs. For a real-host smoke check, see [HANDOFF.md](HANDOFF.md).
