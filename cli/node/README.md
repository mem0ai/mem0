# mem0 CLI (Node.js)

The official command-line interface for [mem0](https://mem0.ai) — the memory layer for AI agents. TypeScript implementation.

> **Built for AI agents.** Pass `--agent` (or `--json`) as a global flag on any command to get structured JSON output optimized for programmatic consumption — sanitized fields, no colors or spinners, and errors as JSON too.

## Prerequisites

- Node.js **18+**
- pnpm (`npm install -g pnpm`) — for development only

## Installation

```bash
npm install -g @mem0/cli
```

## Quick start

```bash
# Interactive setup wizard
mem0 init

# Or login via email
mem0 init --email alice@company.com

# Or authenticate with an existing API key
mem0 init --api-key m0-xxx

# Add a memory
mem0 add "I prefer dark mode and use vim keybindings" --user-id alice

# Search memories
mem0 search "What are Alice's preferences?" --user-id alice

# List all memories for a user
mem0 list --user-id alice

# Get a specific memory
mem0 get <memory-id>

# Update a memory
mem0 update <memory-id> "I switched to light mode"

# Delete a memory
mem0 delete <memory-id>
```

## Commands

### `mem0 init`

Interactive setup wizard. Prompts for your API key and default user ID.

```bash
mem0 init
mem0 init --api-key m0-xxx --user-id alice
mem0 init --email alice@company.com
```

If an existing configuration is detected, the CLI asks for confirmation before overwriting. Use `--force` to skip the prompt (useful in CI/CD).

```bash
mem0 init --api-key m0-xxx --user-id alice --force
```

| Flag | Description |
|------|-------------|
| `--api-key` | API key (skip prompt) |
| `-u, --user-id` | Default user ID (skip prompt) |
| `--email` | Login via email verification code |
| `--code` | Verification code (use with `--email` for non-interactive login) |
| `--force` | Overwrite existing config without confirmation |

### `mem0 add`

Add a memory from text, a JSON messages array, a file, or stdin.

```bash
mem0 add "I prefer dark mode" --user-id alice
mem0 add --file conversation.json --user-id alice
echo "Loves hiking on weekends" | mem0 add --user-id alice
```

| Flag | Description |
|------|-------------|
| `-u, --user-id` | Scope to a user |
| `--agent-id` | Scope to an agent |
| `--messages` | Conversation messages as JSON |
| `-f, --file` | Read messages from a JSON file |
| `-m, --metadata` | Custom metadata as JSON |
| `--categories` | Categories (JSON array or comma-separated) |
| `--graph / --no-graph` | Enable or disable graph memory extraction |
| `-o, --output` | Output format: `text`, `json`, `quiet` |

### `mem0 search`

Search memories using natural language.

```bash
mem0 search "dietary restrictions" --user-id alice
mem0 search "preferred tools" --user-id alice --output json --top-k 5
```

| Flag | Description |
|------|-------------|
| `-u, --user-id` | Filter by user |
| `-k, --top-k` | Number of results (default: 10) |
| `--threshold` | Minimum similarity score (default: 0.3) |
| `--rerank` | Enable reranking |
| `--keyword` | Use keyword search instead of semantic |
| `--filter` | Advanced filter expression (JSON) |
| `--graph / --no-graph` | Enable or disable graph in search |
| `-o, --output` | Output format: `text`, `json`, `table` |

### `mem0 list`

List memories with optional filters and pagination.

```bash
mem0 list --user-id alice
mem0 list --user-id alice --category preferences --output json
mem0 list --user-id alice --after 2024-01-01 --page-size 50
```

| Flag | Description |
|------|-------------|
| `-u, --user-id` | Filter by user |
| `--page` | Page number (default: 1) |
| `--page-size` | Results per page (default: 100) |
| `--category` | Filter by category |
| `--after` | Created after date (YYYY-MM-DD) |
| `--before` | Created before date (YYYY-MM-DD) |
| `-o, --output` | Output format: `text`, `json`, `table` |

### `mem0 get`

Retrieve a specific memory by ID.

```bash
mem0 get 7b3c1a2e-4d5f-6789-abcd-ef0123456789
mem0 get 7b3c1a2e-4d5f-6789-abcd-ef0123456789 --output json
```

### `mem0 update`

Update the text or metadata of an existing memory.

```bash
mem0 update <memory-id> "Updated preference text"
mem0 update <memory-id> --metadata '{"priority": "high"}'
echo "new text" | mem0 update <memory-id>
```

### `mem0 delete`

Delete a single memory, all memories for a scope, or an entire entity.

```bash
# Delete a single memory
mem0 delete <memory-id>

# Delete all memories for a user
mem0 delete --all --user-id alice --force

# Delete all memories project-wide
mem0 delete --all --project --force

# Preview what would be deleted
mem0 delete --all --user-id alice --dry-run
```

| Flag | Description |
|------|-------------|
| `--all` | Delete all memories matching scope filters |
| `--entity` | Delete the entity and all its memories |
| `--project` | With `--all`: delete all memories project-wide |
| `--dry-run` | Preview without deleting |
| `--force` | Skip confirmation prompt |

### `mem0 import`

Bulk import memories from a JSON file.

```bash
mem0 import data.json --user-id alice
```

The file should be a JSON array where each item has a `memory` (or `text` or `content`) field and optional `user_id`, `agent_id`, and `metadata` fields.

### `mem0 config`

View or modify the local CLI configuration.

```bash
mem0 config show              # Display current config (secrets redacted)
mem0 config get api_key       # Get a specific value
mem0 config set user_id bob   # Set a value
```

### `mem0 entity`

List or delete entities (users, agents, apps, runs).

```bash
mem0 entity list users
mem0 entity list agents --output json
mem0 entity delete --user-id alice --force
```

### `mem0 event`

Inspect background processing events created by async operations (e.g. bulk deletes, large add jobs).

```bash
# List recent events
mem0 event list

# Check the status of a specific event
mem0 event status <event-id>
```

| Flag | Description |
|------|-------------|
| `-o, --output` | Output format: `text`, `json` |

### `mem0 status`

Verify your API connection and display the current project.

```bash
mem0 status
```

### `mem0 version`

Print the CLI version.

```bash
mem0 version
```

## Agent mode

Pass `--agent` (or its alias `--json`) as a **global flag** on any command to get output designed for AI agent tool loops:

```bash
mem0 --agent search "user preferences" --user-id alice
mem0 --agent add "User prefers dark mode" --user-id alice
mem0 --agent list --user-id alice
mem0 --agent delete --all --user-id alice --force
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

## Global flags

These flags are available on all commands:

| Flag | Description |
|------|-------------|
| `--json` | Enable agent mode: structured JSON envelope output, no colors or spinners |
| `--agent` | Alias for `--json` |
| `--api-key` | Override the configured API key for this request |
| `--base-url` | Override the configured API base URL for this request |
| `-o, --output` | Set the output format |

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

Environment variables take precedence over values in the config file, which take precedence over defaults.

## Development

```bash
cd cli/node
pnpm install

# Development mode (runs TypeScript directly, no build needed)
pnpm dev --help
pnpm dev add "test memory" --user-id alice
pnpm dev search "test" --user-id alice

# Or build first, then run the compiled JS
pnpm build
node dist/index.js --help
```

## Documentation

Full documentation is available at [docs.mem0.ai/platform/cli](https://docs.mem0.ai/platform/cli).

## License

Apache-2.0
