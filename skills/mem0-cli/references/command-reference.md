# Mem0 CLI Command Reference

Complete reference for every command, argument, flag, and output mode in the mem0 CLI. Both the Node.js (`@mem0/cli`) and Python (`mem0-cli`) implementations are identical in behavior.

---

## Global Options

These options are available on every command:

| Flag | Type | Description |
|------|------|-------------|
| `--json` / `--agent` | boolean | Agent mode: wrap all output in a structured JSON envelope on stdout. Spinners and progress go to stderr. |
| `-o, --output <format>` | string | Output format. Supported values vary per command (see matrix below). |
| `--api-key <key>` | string | Override the API key for this invocation. Takes precedence over env var and config file. |
| `--base-url <url>` | string | Override the API base URL (default: `https://api.mem0.ai`). |
| `--version` | boolean | Print version and exit. |

---

## Commands

### `mem0 init`

Interactive setup wizard. Configures API key and default user ID.

**Usage:** `mem0 init [OPTIONS]`

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--api-key <key>` | string | - | API key (skip interactive prompt). |
| `-u, --user-id <id>` | string | - | Default user ID (skip interactive prompt). |
| `--email <addr>` | string | - | Login via email verification code instead of API key. |
| `--code <code>` | string | - | Verification code (use with `--email` for fully non-interactive login). |
| `--force` | boolean | false | Overwrite existing config without confirmation. |

**Behavior:**

- If `~/.mem0/config.json` already exists with an API key, warns and asks for confirmation (or errors in non-TTY unless `--force` is set).
- **Email login flow** (`--email`): sends a 6-digit code to the email via `POST /api/v1/auth/email_code/`. If `--code` is also given, verifies immediately. On success, saves API key, org_id, and project_id. Cannot be combined with `--api-key`.
- **API key flow**: if both `--api-key` and `--user-id` are given, runs fully non-interactively. Otherwise prompts for missing values.
- In non-TTY without sufficient flags, prints a usage hint and exits with error.

**Examples:**
```bash
mem0 init
mem0 init --api-key m0-xxx --user-id alice
mem0 init --api-key m0-xxx --user-id alice --force
mem0 init --email alice@company.com
mem0 init --email alice@company.com --code 482901
```

---

### `mem0 add`

Add a memory from text, messages, file, or stdin.

**Usage:** `mem0 add [text] [OPTIONS]`

**Arguments:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `text` | string | No | Text content to add as a memory. |

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-u, --user-id <id>` | string | - | Scope to user. |
| `--agent-id <id>` | string | - | Scope to agent. |
| `--app-id <id>` | string | - | Scope to app. |
| `--run-id <id>` | string | - | Scope to run. |
| `--messages <json>` | string | - | Conversation messages as JSON array (e.g. `'[{"role":"user","content":"..."}]'`). |
| `-f, --file <path>` | path | - | Read messages from a JSON file. |
| `-m, --metadata <json>` | string | - | Custom metadata as JSON object (e.g. `'{"source":"cli"}'`). |
| `--no-infer` | boolean | false | Skip inference; store the text verbatim. |
| `--categories <cats>` | string | - | Categories as JSON array or comma-separated string. |
| `-o, --output <fmt>` | string | `text` | Output format: `text`, `json`, `quiet`. |

**Input priority:** `--file` > `--messages` > text argument > stdin (if piped and no text).

Text content is wrapped as `[{"role": "user", "content": "<text>"}]` before sending to the API. Messages from `--messages` or `--file` are sent as-is.

**Output events:** The API returns results with an `event` field per memory:

| Event | Meaning |
|-------|---------|
| `ADD` | New memory created |
| `UPDATE` | Existing memory updated (deduplication) |
| `DELETE` | Existing memory removed (contradiction) |
| `NOOP` | No change needed |
| `PENDING` | Processing asynchronously in background |

**Examples:**
```bash
mem0 add "I prefer dark mode" --user-id alice
mem0 add "allergic to nuts" -u alice -m '{"source":"onboarding"}'
mem0 add --messages '[{"role":"user","content":"I like Python"}]' -u alice
mem0 add --file conversation.json -u alice -o json
echo "I prefer dark mode" | mem0 add -u alice
mem0 add "temporary note" -u alice --expires 2025-12-31
mem0 add "important fact" -u alice --immutable
mem0 add "uses vim" -u alice --categories "tools,preferences"
```

---

### `mem0 search`

Search memories by semantic query.

**Usage:** `mem0 search <query> [OPTIONS]`

**Arguments:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | Yes | The search query. Falls back to stdin if piped. |

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-u, --user-id <id>` | string | - | Filter by user. |
| `--agent-id <id>` | string | - | Filter by agent. |
| `--app-id <id>` | string | - | Filter by app. |
| `--run-id <id>` | string | - | Filter by run. |
| `-k, --top-k, --limit <n>` | integer | 10 | Maximum number of results to return. |
| `--threshold <score>` | float | 0.1 | Minimum similarity score (0.0 to 1.0). |
| `--rerank` | boolean | false | Enable reranking for improved relevance (Platform only). |
| `--filter <json>` | string | - | Advanced filter expression as JSON (AND/OR operators). |
| `--fields <list>` | string | - | Comma-separated list of fields to return. |
| `-o, --output <fmt>` | string | `text` | Output format: `text`, `json`, `table`. |

**Examples:**
```bash
mem0 search "preferences" --user-id alice
mem0 search "tools" -u alice -o json -k 5
mem0 search "dietary restrictions" -u alice --threshold 0.5
mem0 search "project setup" -u alice --rerank
mem0 search "preferences" -u alice --filter '{"categories":{"contains":"food"}}'
echo "preferences" | mem0 search -u alice
```

---

### `mem0 get`

Get a specific memory by ID.

**Usage:** `mem0 get <memory_id> [OPTIONS]`

**Arguments:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `memory_id` | string | Yes | The UUID of the memory to retrieve. |

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-o, --output <fmt>` | string | `text` | Output format: `text`, `json`. |

**Examples:**
```bash
mem0 get abc-123-def-456
mem0 get abc-123-def-456 -o json
```

---

### `mem0 list`

List memories with optional filters and pagination.

**Usage:** `mem0 list [OPTIONS]`

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-u, --user-id <id>` | string | - | Filter by user. |
| `--agent-id <id>` | string | - | Filter by agent. |
| `--app-id <id>` | string | - | Filter by app. |
| `--run-id <id>` | string | - | Filter by run. |
| `--page <n>` | integer | 1 | Page number. |
| `--page-size <n>` | integer | 100 | Results per page. |
| `--category <name>` | string | - | Filter by category. |
| `--after <date>` | string | - | Created after (YYYY-MM-DD). |
| `--before <date>` | string | - | Created before (YYYY-MM-DD). |
| `-o, --output <fmt>` | string | `table` | Output format: `text`, `json`, `table`. |

**Examples:**
```bash
mem0 list -u alice
mem0 list --category prefs --after 2024-01-01 -o json
mem0 list -u alice --page 2 --page-size 50
mem0 list --before 2024-06-01 -o table
```

---

### `mem0 update`

Update a memory's text or metadata.

**Usage:** `mem0 update <memory_id> [text] [OPTIONS]`

**Arguments:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `memory_id` | string | Yes | The UUID of the memory to update. |
| `text` | string | No | New memory text. Falls back to stdin if piped and no `--metadata`. |

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-m, --metadata <json>` | string | - | Update metadata as JSON object. |
| `-o, --output <fmt>` | string | `text` | Output format: `text`, `json`, `quiet`. |

**Examples:**
```bash
mem0 update abc-123 "new text"
mem0 update abc-123 --metadata '{"priority":"high"}'
mem0 update abc-123 "new text" -m '{"priority":"high"}'
echo "new text" | mem0 update abc-123
```

---

### `mem0 delete`

Delete a memory, all memories matching a scope, or an entity. This command has three mutually exclusive modes.

**Usage:** `mem0 delete [memory_id] [OPTIONS]`

**Arguments:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `memory_id` | string | No | Memory ID to delete (omit when using `--all` or `--entity`). |

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--all` | boolean | false | Delete all memories matching scope filters. |
| `--entity` | boolean | false | Delete the entity itself and all its memories (cascade). |
| `--project` | boolean | false | With `--all`: delete ALL memories project-wide (sends wildcard IDs). |
| `--dry-run` | boolean | false | Show what would be deleted without actually deleting. |
| `--force` | boolean | false | Skip confirmation prompt. |
| `-u, --user-id <id>` | string | - | Scope to user. |
| `--agent-id <id>` | string | - | Scope to agent. |
| `--app-id <id>` | string | - | Scope to app. |
| `--run-id <id>` | string | - | Scope to run. |
| `-o, --output <fmt>` | string | `text` | Output format: `text`, `json`, `quiet`. |

**Three modes (mutually exclusive):**

1. **Single memory:** `mem0 delete <memory_id>` -- deletes one memory by its UUID.
2. **Bulk delete:** `mem0 delete --all [scope flags]` -- deletes all memories matching the scope. Add `--project` to wipe all memories project-wide (sends wildcard `*` entity IDs).
3. **Entity cascade:** `mem0 delete --entity [scope flags]` -- deletes the entity itself AND all its memories.

You cannot combine `<memory_id>` with `--all` or `--entity`, and you cannot combine `--all` with `--entity`. If none of these are provided, the command prints a usage hint and exits with an error.

**Dry-run behavior:**
- Single: fetches the memory, displays it, prints "No changes made."
- `--all`: lists matching memories with count, prints "No changes made."
- `--entity`: shows the affected scope without deleting.

**Confirmation:** Without `--force`, all destructive modes prompt `[y/N]`. With `--all --project`, the prompt explicitly warns about project-wide deletion.

**`--all --project` behavior:** Sends `DELETE /v1/memories/` with `user_id=*&agent_id=*&app_id=*&run_id=*`. The API returns an async response. The CLI prints "Deletion started. Memories will be removed in the background."

**Examples:**
```bash
mem0 delete abc-123-def-456
mem0 delete --all -u alice --force
mem0 delete --all --project --force
mem0 delete --entity -u alice --force
mem0 delete abc-123 --dry-run
mem0 delete --all -u alice --dry-run
```

---

### `mem0 import`

Import memories from a JSON file.

**Usage:** `mem0 import <file_path> [OPTIONS]`

**Arguments:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file_path` | string | Yes | Path to a JSON file containing memories. |

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-u, --user-id <id>` | string | - | Override user ID for all imported items. |
| `--agent-id <id>` | string | - | Override agent ID for all imported items. |
| `-o, --output <fmt>` | string | `text` | Output format: `text`, `json`. |

**File format:** A JSON array (or single object) where each item has a `memory`, `text`, or `content` field for the text, plus optional `user_id`, `agent_id`, and `metadata` fields. CLI-provided `--user-id` and `--agent-id` override per-item values.

**Import format example:**
```json
[
  { "memory": "Prefers dark mode", "user_id": "alice" },
  { "text": "Allergic to nuts", "metadata": { "source": "intake" } },
  { "content": "Uses VS Code" }
]
```

**Behavior:** Iterates through items, calling the add API for each. Displays progress and reports `added` and `failed` counts on completion.

**Examples:**
```bash
mem0 import memories.json --user-id alice
mem0 import data.json -u alice -o json
```

---

### `mem0 config show`

Display current configuration with secrets redacted.

**Usage:** `mem0 config show [OPTIONS]`

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-o, --output <fmt>` | string | `text` | Output format: `text`, `json`. |

**Examples:**
```bash
mem0 config show
mem0 config show -o json
```

---

### `mem0 config get`

Get a single configuration value.

**Usage:** `mem0 config get <key>`

**Arguments:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `key` | string | Yes | Dotted config key (e.g. `platform.api_key`, `defaults.user_id`). |

**Valid keys:** `platform.api_key`, `platform.base_url`, `defaults.user_id`, `defaults.agent_id`, `defaults.app_id`, `defaults.run_id`.

API key values are always redacted in output.

**Examples:**
```bash
mem0 config get platform.api_key
mem0 config get defaults.user_id
```

---

### `mem0 config set`

Set a configuration value.

**Usage:** `mem0 config set <key> <value>`

**Arguments:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `key` | string | Yes | Dotted config key (e.g. `defaults.user_id`). |
| `value` | string | Yes | Value to set. |

**Type coercion:** Boolean fields accept `true`/`1`/`yes` (case-insensitive) as true, anything else as false.

**Examples:**
```bash
mem0 config set defaults.user_id alice
mem0 config set platform.base_url https://api.mem0.ai
```

---

### `mem0 config clear`

Clear the configuration file. Removes `~/.mem0/config.json`.

**Usage:** `mem0 config clear`

**Examples:**
```bash
mem0 config clear
```

---

### `mem0 entity list`

List all entities of a given type.

**Usage:** `mem0 entity list <entity_type> [OPTIONS]`

**Arguments:**

| Name | Type | Required | Choices | Description |
|------|------|----------|---------|-------------|
| `entity_type` | string | Yes | `users`, `agents`, `apps`, `runs` | Entity type to list. |

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-o, --output <fmt>` | string | `table` | Output format: `table`, `json`. |

**Behavior:** Calls `GET /v1/entities/` (returns all types), then filters client-side using the type map (`users` -> `user`, `agents` -> `agent`, etc.). Displays a table with "Name / ID" and "Created" columns.

**Examples:**
```bash
mem0 entity list users
mem0 entity list agents -o json
```

---

### `mem0 entity delete`

Delete an entity and ALL its memories (cascade).

**Usage:** `mem0 entity delete [OPTIONS]`

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-u, --user-id <id>` | string | - | User ID of the entity to delete. |
| `--agent-id <id>` | string | - | Agent ID of the entity to delete. |
| `--app-id <id>` | string | - | App ID of the entity to delete. |
| `--run-id <id>` | string | - | Run ID of the entity to delete. |
| `--dry-run` | boolean | false | Show what would be deleted without deleting. |
| `--force` | boolean | false | Skip confirmation prompt. |
| `-o, --output <fmt>` | string | `text` | Output format: `text`, `json`, `quiet`. |

At least one entity ID is required. Errors if none provided.

**Examples:**
```bash
mem0 entity delete --user-id alice --force
mem0 entity delete --user-id alice --dry-run
mem0 entity delete --agent-id bot1 --force
```

---

### `mem0 event list`

List recent background processing events.

**Usage:** `mem0 event list [OPTIONS]`

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-o, --output <fmt>` | string | `table` | Output format: `text` (table), `json`. |

**Behavior:** Fetches all events for the project. Displays a table with columns: Event ID (first 8 chars), Type, Status (color-coded), Latency, Created. Status values: `PENDING`, `SUCCEEDED`, `FAILED`, `PROCESSING`.

**Examples:**
```bash
mem0 event list
mem0 event list --output json
```

---

### `mem0 event status`

Get the status and results of a specific background event.

**Usage:** `mem0 event status <event_id> [OPTIONS]`

**Arguments:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `event_id` | string | Yes | Event ID to inspect. |

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-o, --output <fmt>` | string | `text` | Output format: `text`, `json`. |

**Behavior:** Fetches the event by ID. Displays: Event ID, Type, Status, Latency, Created, Updated, and a list of result memories.

**Examples:**
```bash
mem0 event status evt-abc-123
mem0 event status evt-abc-123 --output json
```

---

### `mem0 status`

Check connectivity and authentication.

**Usage:** `mem0 status [OPTIONS]`

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-o, --output <fmt>` | string | `text` | Output format: `text`, `json`. |

**Behavior:** Calls `GET /v1/ping/` to validate connectivity and authentication. Displays connection status, backend type, and base URL.

**JSON output:**
```json
{
  "status": "success",
  "command": "status",
  "duration_ms": 112,
  "data": {
    "connected": true,
    "backend": "platform",
    "base_url": "https://api.mem0.ai"
  }
}
```

**Examples:**
```bash
mem0 status
mem0 status -o json
```

---

## Agent Mode Envelope Format

When `--json` or `--agent` is passed, every command wraps its output in a consistent JSON envelope on stdout:

```json
{
  "status": "success",
  "command": "<command_name>",
  "duration_ms": 245,
  "scope": { "user_id": "alice", "agent_id": null },
  "count": 10,
  "error": null,
  "data": { ... }
}
```

**Fields:**
- `status`: `"success"` or `"error"`.
- `command`: The command name (e.g. `"search"`, `"add"`, `"list"`).
- `duration_ms`: Elapsed time in milliseconds (optional).
- `scope`: Active entity scope, omitted if empty (optional).
- `count`: Number of results, where applicable (optional).
- `error`: Error message string, or `null` on success.
- `data`: Command-specific response data, or `null` on error.

**Sanitized data fields per command in agent mode:**

| Command | `data` shape |
|---------|-------------|
| `add` | `[{id, memory, event}]` or `[{status, event_id}]` for PENDING |
| `search` | `[{id, memory, score, created_at, categories}]` |
| `list` | `[{id, memory, created_at, categories}]` |
| `get` | `{id, memory, created_at, updated_at, categories, metadata}` |
| `update` | `{id, memory}` |
| `delete` | Raw API response |
| `entity list` | `[{name, type, count}]` |
| `event list` | `[{id, event_type, status, latency, created_at}]` |
| `event status` | `{id, event_type, status, latency, created_at, updated_at, results}` |
| `status` | `{connected, backend, base_url}` |
| `config show` | Config object (keys redacted) |
| `import` | `{added, failed, duration_s}` |

**Error envelope:**
```json
{
  "status": "error",
  "command": "search",
  "error": "Authentication failed. Your API key may be invalid or expired.",
  "data": null
}
```

---

## Entity ID Resolution

**Rule:** If **any** explicit entity ID is provided via CLI flags (`--user-id`, `--agent-id`, `--app-id`, `--run-id`), the CLI uses only the explicitly provided IDs. It does NOT mix in defaults from config for the other entity types.

If **no** explicit IDs are given, all configured defaults from config file and env vars apply.

**Rationale:** If a user passes `--user-id alice` and the config also has `agent_id=bot1`, they want only Alice's memories -- not the intersection of Alice AND bot1.

```
if any(user_id, agent_id, app_id, run_id) were passed as flags:
    use only the explicitly provided IDs (others = null)
else:
    use all configured defaults
```

This applies to commands with `resolveIds: true`: `add`, `search`, `list`, `delete`, `import`.

---

## Filter Building

For `search` and `list`, entity IDs and additional filters are composed into the API filter structure:

1. If the user provides a pre-built filter via `--filter` containing `AND` or `OR` keys, it is passed through to the API as-is.
2. Otherwise, the CLI builds an array of AND conditions:
   - Each entity ID becomes a condition: `{"user_id": "alice"}`, etc.
   - Category filters: `{"categories": {"contains": "<category>"}}`.
   - Date filters: `{"created_at": {"gte": "YYYY-MM-DD"}}` and/or `{"created_at": {"lte": "YYYY-MM-DD"}}`.
3. If exactly 1 condition: sent as a single object (no wrapping).
4. If 2+ conditions: wrapped as `{"AND": [condition1, condition2, ...]}`.
5. If 0 conditions: no filter sent.

---

## Output Mode Support Matrix

| Command | `text` | `json` | `table` | `quiet` | Default |
|---------|--------|--------|---------|---------|---------|
| `add` | Y | Y | - | Y | `text` |
| `search` | Y | Y | Y | - | `text` |
| `get` | Y | Y | - | - | `text` |
| `list` | Y | Y | Y | - | `table` |
| `update` | Y | Y | - | Y | `text` |
| `delete` | Y | Y | - | Y | `text` |
| `import` | Y | Y | - | - | `text` |
| `config show` | Y | Y | - | - | `text` |
| `config get` | raw | - | - | - | raw |
| `config set` | msg | - | - | - | msg |
| `entity list` | - | Y | Y | - | `table` |
| `entity delete` | Y | Y | - | Y | `text` |
| `event list` | Y (table) | Y | - | - | `table` |
| `event status` | Y | Y | - | - | `text` |
| `status` | Y | Y | - | - | `text` |

All commands additionally support agent mode (`--json`/`--agent`) which overrides the output format with the JSON envelope.
