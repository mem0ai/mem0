# Mem0 for Hermes Agent

Persistent memory for [Hermes Agent](https://github.com/NousResearch/hermes-agent), powered by [Mem0](https://mem0.ai).

This standalone plugin recalls relevant memories before a response and extracts facts from conversations afterward. It works alongside Hermes' file-based memory and supports Mem0 Cloud, a self-hosted Mem0 server, or the in-process OSS SDK.

## Features

- **Automatic recall and capture** across conversations.
- **Four agent tools** to search, add, update, and delete memories.
- **Three backend modes** with interactive setup through `hermes memory setup`.
- **User-scoped memories** with agent and channel metadata on writes.

## Setup

### 1. Install

Requires [Hermes Agent](https://github.com/NousResearch/hermes-agent) with memory-provider plugin support and Python 3.11 or later. After this directory is merged to Mem0's main branch:

```bash
hermes plugins install mem0ai/mem0/integrations/hermes-plugin-mem0
hermes plugins enable mem0
```

Hermes installers with plugin dependency support install `mem0ai>=2.0.10,<3` and `httpx>=0.27,<1` from this directory's `pyproject.toml`. On older hosts such as Hermes v0.21.3, install those requirements into the **Hermes Python environment** explicitly. The OSS setup wizard installs additional provider packages as needed.

> Hermes versions that still bundle Mem0 prefer the bundled provider. Use a Hermes release that has completed the standalone-provider migration; installing this plugin alone does not replace the bundled implementation. See [Existing users and migration](#existing-users-and-migration).

### 2. Configure

```bash
hermes memory setup mem0
```

Run this in an interactive terminal and choose a backend:

| Mode | What you need |
|------|----------------|
| **Platform** (default) | A Mem0 API key from [app.mem0.ai](https://app.mem0.ai/dashboard/api-keys) |
| **Self-hosted server** | A running [Mem0 server](../../server), its URL, and its API key unless authentication is disabled |
| **OSS** | An LLM, embedder, and vector store; no Mem0 API key needed |

For a self-hosted server, choose **Self-hosted server** and enter its URL and API key. Requests use `X-API-Key` and the server's `/search` and `/memories` routes. Setting `host` selects this backend unless `mode` is `oss`.

For the in-process SDK, choose **Open Source**. The wizard offers OpenAI or Ollama and local Qdrant or PGVector. Use manual configuration for custom OpenAI-compatible endpoints, deployment names, or a Qdrant server. OSS does not use Mem0 Cloud; data still goes to whichever model services you configure. Run setup again to switch modes. When switching to Platform, remove any stale `MEM0_HOST` setting from the environment and profile `.env`.

Desktop sessions in the same process and profile share local Qdrant storage when their OSS settings match. Operations are serialized, and storage closes after the last session releases it. Conflicting settings are rejected without changing existing memories; close the active sessions before changing models or credentials. Use a Qdrant server or the self-hosted Mem0 HTTP API when separate processes (for example, CLI and Desktop together) need the same store.

Hermes hosts whose `hermes memory setup --help` lists only a provider argument reject options such as `--mode`, `--host`, and `--oss-llm` before the plugin runs. Use the interactive command above, or the [manual profile configuration](https://docs.mem0.ai/integrations/hermes) for unattended setup. Redirected input cannot select the mode picker; it falls back to Platform.

### 3. Verify

```bash
hermes memory status
```

Start a fresh Hermes conversation and ask it to remember a fact, then search for that fact in a later session using the same user identity.

## Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `mem0_search` | Search memories by meaning | `query`, optional `top_k` (default 10, max 50) and `rerank` (Platform only) |
| `mem0_add` | Store text verbatim, without fact extraction | `content` |
| `mem0_update` | Update a memory's text | `memory_id`, `text` |
| `mem0_delete` | Delete a memory | `memory_id` |

## Configuration

Settings live in `$HERMES_HOME/mem0.json`; the default Hermes home is `~/.hermes`. Setup normally stores API keys in that profile's `.env`. Distinct OpenAI LLM/embedder keys and database credentials are stored in the OSS configuration. Setup writes both files atomically with owner-only permissions.

| Key | Default | Description |
|-----|---------|-------------|
| `mode` | `platform` | `platform` for Cloud/server routing, or `oss` for the in-process SDK |
| `host` | unset | Self-hosted server URL; ignored in OSS mode |
| `user_id` | gateway user ID, then `hermes-user` | Set a stable ID to share memories across gateways |
| `agent_id` | `hermes` | Agent identifier attached to writes |
| `rerank` | `false` | Platform reranking for automatic recall and tool searches that omit `rerank` |
| `sync_max_chars` | `450` | Maximum characters per user/assistant message sent for automatic extraction |
| `oss` | `{}` | OSS LLM, embedder, and vector-store configuration written by setup |

`MEM0_MODE`, `MEM0_HOST`, `MEM0_USER_ID`, and `MEM0_AGENT_ID` provide environment defaults; non-empty file settings override them. `MEM0_API_KEY` supplies the Cloud or server key when `api_key` is not set in the file.

An explicit `user_id` other than `hermes-user` takes precedence over a gateway's native user ID. Searches use that user identity across sessions; writes attach `agent_id` and `metadata.channel`.

## Automatic recall and capture

Recall waits up to three seconds for memories relevant to the current message. If results are late, the model can still call `mem0_search`.

After a turn, a background worker sends the user message and assistant response for extraction. Each message is truncated to **450 characters by default in every mode**, preferring a sentence boundary. Increase `sync_max_chars` to suit your model's context limit. Explicit `mem0_add` calls store their supplied text verbatim.

Capture is best effort: if the previous sync remains busy after a five-second wait, the new turn is skipped. There is no durable queue. Five consecutive backend failures pause calls for two minutes before retrying.

Graceful shutdown waits for active recall and capture workers before closing the backend, including at Python process exit. Backend network timeouts still apply: self-hosted HTTP capture has a 120-second read timeout and a 30-second connection timeout; other self-hosted HTTP operations use 30 seconds. Forced termination, including Hermes' 30-second exit watchdog, can still interrupt pending writes.

## Existing users and migration

Keep `memory.provider: mem0`, your existing `mem0.json`, `MEM0_*` settings, user identity, and OSS storage paths. Moving the plugin does not require moving memories or rerunning setup.

Automatic migration also requires coordination in Hermes:

1. A Hermes build containing [migration support from PR #114569](https://github.com/NousResearch/hermes-agent/pull/114569).
2. An approved catalog entry named `mem0`, pointing to `https://github.com/mem0ai/mem0`, with `subdir: integrations/hermes-plugin-mem0` and a reviewed full commit SHA.
3. Removal of Hermes' bundled Mem0 provider, which otherwise takes precedence.

With those in place, Hermes can install a missing configured provider during `hermes update` or at agent startup. Startup installation respects `security.allow_lazy_installs`; disabled or offline installation requires manual action. Merging this directory alone does not register the catalog entry or complete rollout.

The plugin supports CLI setup/status. It does not include a Desktop configuration panel or provider-specific CLI commands.

## Troubleshooting

- **Mem0 unavailable:** run `hermes memory status`. Check the API key and backend connectivity; after five consecutive failures the circuit breaker waits two minutes.
- **Memories missing:** confirm the same user identity across sessions and check `sync_max_chars`. Automatic extraction may omit facts; use `mem0_add` to store exact text.
- **OSS connection refused:** check the configured model/vector service, or filesystem permissions for local Qdrant.
- **Embedding dimension mismatch:** initialization fails without deleting existing data. Restore the previous embedding model/dimensions, or use a new collection and migrate data explicitly.

## Development

From the Mem0 repository root, with `ruff` and `isort` installed:

```bash
ruff check integrations/hermes-plugin-mem0
isort --check-only --profile black integrations/hermes-plugin-mem0
```

Validate changes in an isolated Hermes profile using live CLI and Desktop sessions. Check memory
add/search/update/delete, automatic capture and recall, overlapping Desktop sessions, and persistence after restart.

## License

[Apache-2.0](LICENSE) for Mem0 contributions. Includes code from [Nous Research's standalone Mem0 provider](https://github.com/NousResearch/hermes-plugin-mem0/tree/3fc36950b2b7c19cdd81c6de99f10d2cbed850af) under MIT; its original license and copyright notice are preserved in the third-party section of [LICENSE](LICENSE).
