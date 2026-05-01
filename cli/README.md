# mem0 CLI

The official command-line interface for [mem0](https://mem0.ai) — the memory layer for AI agents. Works with the Mem0 Platform API. Available in Python and Node.js.

> **For AI agents:** pass `--agent` (or `--json`) on any command for structured JSON output purpose-built for tool loops — sanitized fields, no colors or spinners, errors as JSON. See [Agent mode](#agent-mode) below.

## Installation

```bash
npm install -g @mem0/cli
```

```bash
pip install mem0-cli
```

Both packages install a `mem0` binary with identical behavior.

## Quick start

```bash
# Interactive setup wizard
mem0 init

# Or login via email (get a new API key)
mem0 init --email alice@company.com

# Or authenticate with an existing API key
mem0 init --api-key m0-xxx

# Add a memory
mem0 add "I prefer dark mode and use vim keybindings" --user-id alice

# Search memories
mem0 search "What are Alice's preferences?" --user-id alice

# List all memories for a user
mem0 list --user-id alice

# Update a memory
mem0 update <memory-id> "I switched to light mode"

# Delete a memory
mem0 delete <memory-id>
```

## Commands

| Command | Description |
|---------|-------------|
| `mem0 init` | Setup wizard — login via email or configure API key manually |
| `mem0 add` | Add a memory from text, JSON messages, a file, or stdin |
| `mem0 search` | Search memories using natural language |
| `mem0 list` | List memories with optional filters and pagination |
| `mem0 get` | Retrieve a specific memory by ID |
| `mem0 update` | Update the text or metadata of a memory |
| `mem0 delete` | Delete a memory, all memories for a scope, or an entity |
| `mem0 import` | Bulk import memories from a JSON file |
| `mem0 config` | View or modify CLI configuration |
| `mem0 entity` | List or delete entities (users, agents, apps, runs) |
| `mem0 event` | Inspect background processing events (bulk deletes, large add jobs) |
| `mem0 status` | Verify API connection and display current project |
| `mem0 version` | Print the CLI version |

Run `mem0 <command> --help` for detailed usage on any command.

## Agent mode

Pass `--agent` (or its alias `--json`) as a **global flag** on any command to get output designed for AI agent tool loops:

```bash
mem0 --agent search "user preferences" --user-id alice
mem0 --agent add "User prefers dark mode" --user-id alice
mem0 --agent list --user-id alice
```

Every command returns the same envelope shape:

```json
{
  "status": "success",
  "command": "search",
  "duration_ms": 134,
  "scope": { "user_id": "alice" },
  "count": 2,
  "data": [
    { "id": "abc-123", "memory": "User prefers dark mode", "score": 0.97, "created_at": "2026-01-15", "categories": ["preferences"] }
  ]
}
```

What agent mode does differently from `--output json`:
- **Sanitized `data`**: only the fields an agent needs (id, memory, score, etc.) — no internal API noise
- **No human output**: spinners, colors, and banners are suppressed entirely
- **Errors as JSON**: errors go to stdout as `{"status": "error", "command": "...", "error": "..."}` with a non-zero exit code

Use `mem0 help --json` to get the full command tree as JSON — useful for agents that need to self-discover available commands.

## Output formats

Control how results are displayed with `--output`:

| Format | Description |
|--------|-------------|
| `text` | Human-readable with colors and formatting (default) |
| `json` | Structured JSON for piping to `jq` (raw API response) |
| `table` | Tabular format (default for `list`) |
| `quiet` | Minimal — just IDs or status codes |
| `agent` | Structured JSON envelope with sanitized fields (set by `--agent`/`--json`) |

## Environment variables

| Variable | Description |
|----------|-------------|
| `MEM0_API_KEY` | API key (overrides config file) |
| `MEM0_BASE_URL` | API base URL |
| `MEM0_USER_ID` | Default user ID |
| `MEM0_AGENT_ID` | Default agent ID |
| `MEM0_APP_ID` | Default app ID |
| `MEM0_RUN_ID` | Default run ID |
| `MEM0_ENABLE_GRAPH` | Enable graph memory (`true` / `false`) |

## Implementations

| Language | Directory | Package | Docs |
|----------|-----------|---------|------|
| TypeScript | [`node/`](./node/) | `@mem0/cli` | [README](./node/README.md) |
| Python | [`python/`](./python/) | `mem0-cli` | [README](./python/README.md) |

## Documentation

Full documentation is available at [docs.mem0.ai/platform/cli](https://docs.mem0.ai/platform/cli).

## License

Apache-2.0
