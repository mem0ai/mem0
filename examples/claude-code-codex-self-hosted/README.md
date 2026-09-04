# Claude Code / Codex with self-hosted Mem0

One-click memory integration for AI coding tools backed by a **self-hosted**
Mem0 REST API — no Mem0 Cloud account required.

The repo's `integrations/mem0-plugin` targets the hosted platform
(`MEM0_API_KEY=m0-...` + `https://mcp.mem0.ai/mcp`). Self-hosted users run the
local REST API instead (`MEM0_BASE_URL=http://localhost:8888`,
`X-API-Key` auth) and had no first-party glue. This example fills that gap with
two entry points:

| Entry point | What it does |
|---|---|
| **Lifecycle hooks** (`hooks/`) | Implicit memory: recall relevant memories at session start and per prompt; persist at pre-compact and session end |
| **MCP wrapper** (`mcp/`) | Explicit memory tools (`search_memories`, `add_memory`, `get_memories`, `update_memory`, `delete_memory`) exposed to the agent |

```
┌──────────────────────────────────────────────┐
│ Claude Code / Codex                          │
│                                              │
│  hooks/                 mcp/mem0_mcp_server  │
│  (bash + curl)          (FastMCP stdio)      │
└───────────┬──────────────────────┬───────────┘
            │ REST calls           │ REST calls
            │ (X-API-Key header)   │ (X-API-Key header)
            ▼                      ▼
┌──────────────────────────────────────────────┐
│  Self-hosted Mem0 REST API  (server/)        │
│  http://localhost:8888                       │
└──────────────────────────────────────────────┘
```

## Prerequisites

1. **A running self-hosted Mem0 server.** From the repo root:

   ```bash
   cd server
   make bootstrap        # or: make up, then finish the setup wizard at http://localhost:3000
   ```

   This starts the API on `http://localhost:8888` (OpenAPI docs at
   `http://localhost:8888/docs`) and prints an admin email/password plus the
   first API key.

2. **An API key.** Create one in the dashboard (`Settings → API Keys`) or reuse
   the one printed by `make bootstrap`. Keys look like `m0sk-...`.

3. **`bash`, `curl`, `jq`** for the hooks, and **Python 3.10+** for the MCP
   server. The hooks deliberately use only these three tools — no Python, no
   extra dependencies.

## Quick start (Claude Code)

```bash
# 1. Point the hooks and MCP server at your instance
export MEM0_API_KEY=m0sk-YOUR_KEY
export MEM0_BASE_URL=http://localhost:8888          # already the default
export MEM0_USER_ID=you                             # any stable id
export MEM0_AGENT_ID=my-project                     # per-project scope

# 2. Install the hooks: merge claude-code/settings.json.example
#    into .claude/settings.json (replace <ABS_PATH>)

# 3. Install the MCP server: copy claude-code/.mcp.json.example
#    to the project root as .mcp.json (replace <ABS_PATH> and the key)

# 4. (optional) one-time dependency for the MCP server
pip install "mcp"
```

Start a session. Previous learnings get injected as context, and every
compaction/session end persists what would otherwise be lost.

## Quick start (Codex)

```bash
# 1. Same env exports as above (MEM0_API_KEY, MEM0_BASE_URL, ...)

# 2. Install the hooks: append codex/AGENTS.md.example to the project's
#    AGENTS.md (replace <ABS_PATH>)

# 3. Install the MCP server: merge codex/config.toml.example
#    into ~/.codex/config.toml (replace <ABS_PATH> and the key)

# 4. (optional) one-time dependency for the MCP server
pip install "mcp"
```

## What each hook does

| Hook | Event | Behavior |
|---|---|---|
| `on_session_start.sh` | `SessionStart` | Searches for project/user context and injects the top memories so the session starts with prior knowledge |
| `on_user_prompt.sh` | `UserPromptSubmit` | Searches with the current prompt and injects the top matches (skips replies shorter than 20 chars) |
| `on_pre_compact.sh` | `PostCompact` (Claude Code) / `PreCompact` (Codex) | Tails the transcript and stores it via `POST /memories` — the key persistence point, since this is when context is about to be dropped |
| `on_stop.sh` | `Stop` | Tails the transcript and persists the session's final exchanges |

All hooks **fail open**: if the API key is missing or the server is down, they
exit 0 silently and never block your session.

## Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `MEM0_BASE_URL` | `http://localhost:8888` | Base URL of the self-hosted REST API |
| `MEM0_API_KEY` | *(none — required)* | API key from the self-hosted dashboard |
| `MEM0_USER_ID` | `default` | Stable identifier for the user (scopes all reads/writes) |
| `MEM0_AGENT_ID` | `default` | Identifier for the agent/project (scopes all reads/writes) |
| `MEM0_TOP_K` | `5` | Max results per search |
| `MEM0_THRESHOLD` | `0.0` | Minimum similarity for search results |

## REST endpoints used

| Tool (MCP) | Endpoint |
|---|---|
| `search_memories(query)` | `POST /search` |
| `add_memory(text, infer=True)` | `POST /memories` |
| `get_memories()` | `GET /memories?user_id=...&agent_id=...` |
| `update_memory(memory_id, text)` | `PUT /memories/{memory_id}` |
| `delete_memory(memory_id)` | `DELETE /memories/{memory_id}` |

All requests authenticate with the `X-API-Key` header. The MCP server reads
`MEM0_BASE_URL`, `MEM0_API_KEY`, `MEM0_USER_ID`, and `MEM0_AGENT_ID` from its
environment.

## Security notes

- The API key is a **secret**: prefer exporting `MEM0_API_KEY` in your shell
  over hardcoding it in `.mcp.json` / `config.toml`. The examples show both,
  but the env-var route keeps the key out of your repo.
- Auth is enabled by default on the self-hosted server. `AUTH_DISABLED=true`
  exists for local development only — never use it on a machine you share.
- Hooks are local-only by design: transcripts never leave your machine.
