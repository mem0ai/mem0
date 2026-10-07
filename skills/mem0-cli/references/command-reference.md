# Mem0 CLI Command Reference

Complete reference for every command, argument, flag, and output mode in the mem0 CLI. Both the Node.js (`@mem0/cli`) and Python (`mem0-cli`) implementations share the same commands and flags. Where they differ, the difference is called out inline.

---

## Global Options

Only these two options are global:

| Flag | Type | Description |
|------|------|-------------|
| `--json` / `--agent` | boolean | Agent mode: wrap output in a structured JSON envelope on stdout. Spinners and progress go to stderr (except Node `import`, see its section). Put it before the subcommand (`mem0 --json list`); Python also accepts it anywhere. On `mem0 init`, `--agent` is the Agent Mode bootstrap flag instead (use `--json` there, after the subcommand). |
| `--version` | boolean | Print version and exit. |

These options are declared per command (not global) on `add`, `search`, `get`, `list`, `update`, `delete`, `import`, `status`, `entity list`, `entity delete`, `event list` and `event status`. `config show` takes only `-o`, and `init` takes only `--api-key`.

| Flag | Type | Description |
|------|------|-------------|
| `-o, --output <format>` | string | Output format. Supported values vary per command (see matrix below). |
| `--api-key <key>` | string | Override the API key for this invocation. Takes precedence over env var and config file. |
| `--base-url <url>` | string | Override the API base URL (default: `https://api.mem0.ai`). |

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
| `--agent` | boolean | false | Bootstrap an Agent Mode account (no email required). |
| `--agent-caller <name>` | string | - | Self-declared agent identity for Agent Mode (e.g. `claude-code`, `cursor`). |
| `--source <channel>` | string | - | Channel attribution for signup analytics. |

**Behavior:**

- If `~/.mem0/config.json` already exists with an API key, warns and asks for confirmation. In non-TTY it errors with "Existing config would be overwritten." unless `--force` is set. The Agent Mode path (below) runs before this check.
- **Email login flow** (`--email`): sends a 6-digit code to the email via `POST /api/v1/auth/email_code/`. If `--code` is also given, skips sending and verifies immediately via `/api/v1/auth/email_code/verify/`. In non-TTY without `--code`, the code is sent and the command then errors; re-run with `--code`. On success, saves the API key, `user_email`, and `created_via: "email"`, and sets the default user ID to `--user-id`, else `$USER`/`$USERNAME`, else `mem0-cli`. Cannot be combined with `--api-key`. `--code` without `--email` is an error.
- **Claim flow** (`--email` while the existing config is an unclaimed Agent Mode key): runs the same code flow but claims the existing key to that email. The API key value does not change and memories are kept.
- **API key flow**: if both `--api-key` and `--user-id` are given, runs fully non-interactively (and validates the key against the API). In non-TTY, `--api-key` alone is enough (the user ID defaults to `$USER`/`$USERNAME`/`mem0-cli`). In a TTY with no flags, prompts for the auth method (email or API key), then for the missing values.
- **Agent Mode flow** (`init --agent`, `init --json`, or an agent runtime env var such as `CLAUDECODE` or `CURSOR_AGENT`, with no `--api-key`/`--email`; Python also enters it on a global `mem0 --json init` or `mem0 --agent init`, Node does not): first reuses a valid `MEM0_API_KEY` or a valid key already in config (no new key is minted). Otherwise POSTs to `/api/v1/auth/agent_mode/` and mints a shadow API key in <5s with no email required; the generated `user_<slug>` becomes `defaults.user_id`. Limited to 5 signups per day per network. Pass `--agent-caller <your-name>` to attribute the signup to your AI agent identity. If omitted, run `mem0 identify <your-name>` afterward.
- In non-TTY without `--api-key`, `--email`, or an agent signal, prints "Non-interactive terminal detected and --api-key is required." and exits with error.

**Examples:**
```bash
mem0 init
mem0 init --api-key m0-xxx --user-id alice
mem0 init --api-key m0-xxx --user-id alice --force
mem0 init --email alice@company.com
mem0 init --email alice@company.com --code 482901
mem0 init --agent --agent-caller claude-code   # AI agent self-identifies during bootstrap
```

---

### `mem0 identify`

Tag your active Agent Mode key with the AI agent that's using it. Run this once after `mem0 init --agent` if you didn't pass `--agent-caller`. Idempotent: re-running just overwrites the value.

**Usage:** `mem0 identify <name>`

**Argument:** `<name>`: the AI agent identity (e.g. `claude-code`, `cursor`, `codex`, `cline`, `aider`, or a custom string).

**Behavior:**

- PATCHes `/api/v1/auth/agent_mode/caller/` with `Authorization: Token <current-api-key>` and body `{agent_caller}`.
- Only works on unclaimed agent-mode keys (`platform.agent_mode=true` in config). Errors with "No API key configured." if no key is set, or "This command only works on unclaimed agent-mode keys." otherwise.
- Backend sanitizes the value: lowercases, drops anything outside `[a-z0-9._/-]`, truncates to 32 chars.

**Examples:**
```bash
mem0 identify claude-code
mem0 identify cursor
mem0 identify my-custom-bot
```

---

### `mem0 whoami`

Print your AGENTRUSH identifier (`platform.default_user_id` from config). Errors with "No default_user_id found. Run `mem0 init --agent` first." if none is stored.

**Usage:** `mem0 whoami`

---

### `mem0 agent-rush add|search`

Commands for the AGENTRUSH event game. Memories are public to other players, so never include real names, emails, secrets, or PII.

**Usage:** `mem0 agent-rush add <content>` and `mem0 agent-rush search <query>`

- `add`: content must be 50-1000 characters with no URLs. The server requires 3 searches before adding and caps each key at 3 lifetime searches and 3 lifetime adds.
- Requires an API key from config or `MEM0_API_KEY` (otherwise errors with "Not initialized. Run `mem0 init --agent` first."). Node joins unquoted words into one string; Python takes a single quoted argument.

**Examples:**
```bash
mem0 agent-rush search "constraint satisfaction"
mem0 agent-rush add "I enjoy solving constraint-satisfaction problems and writing small solvers."
```

---

### `mem0 version`

Print the CLI version. `mem0 --version` does the same.

---

### `mem0 help`

**Usage:** `mem0 help [--json]`

Prints the command overview. `--json` (or global `--json`/`--agent`) prints a machine-readable command spec. In both CLIs this spec is hand-maintained and can lag behind the real option list, so trust `mem0 <command> --help` and this reference over it.

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
| `--expires <date>` | string | - | Expiration date (YYYY-MM-DD). Must be in the future. |
| `--immutable` | boolean | false | Accepted but has no effect on v3: the memory can still be updated and no marker is stored. |
| `--custom-instructions <text>` | string | - | Custom instructions for fact extraction. |
| `--agent-custom-instructions <text>` | string | - | Extraction instructions for agent-scoped memories, overriding the project setting. |
| `--custom-categories <json>` | string | - | Custom categories as a JSON array of `{name: description}` objects. |
| `--structured-data-schema <json>` | string | - | Schema for structured data extraction, as JSON. |
| `--timestamp <unix>` | integer | - | Unix timestamp for the memory. |
| `--categories <value>` | string | - | Rejected with an error. Use `--custom-categories` instead. |
| `-o, --output <fmt>` | string | `text` | Output format: `text`, `json`, `quiet`. |

**Input priority:** `--file` > `--messages` > text argument > stdin (if piped or redirected, no text, and not in `--json`/`--agent` mode).

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
mem0 add "temporary note" -u alice --expires 2027-12-31
mem0 add "uses vim" -u alice --custom-categories '[{"tools":"Editors and developer tooling"}]'
```

---

### `mem0 search`

Search memories by semantic query.

**Usage:** `mem0 search <query> [OPTIONS]`

**Arguments:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | Yes | The search query. Falls back to stdin if piped or redirected (Python skips this in `--json`/`--agent` mode; Node does not). |

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-u, --user-id <id>` | string | - | Filter by user. |
| `--agent-id <id>` | string | - | Filter by agent. |
| `--app-id <id>` | string | - | Filter by app. |
| `--run-id <id>` | string | - | Filter by run. |
| `-k, --top-k <n>` | integer | 10 | Maximum number of results to return (must be >= 1). Python also accepts `--limit` as an alias. |
| `--threshold <score>` | float | 0.3 | Minimum similarity score (0.0 to 1.0), applied before hybrid score blending, so a returned item's displayed `score` can be lower than this value. |
| `--rerank` | boolean | false | Enable reranking for improved relevance (Platform only). |
| `--keyword` | boolean | false | Sent to the API as `keyword_search` but not applied by v3 search, which always blends keyword matching into hybrid scoring. |
| `--filter <json>` | string | - | Advanced filter expression as JSON. If it contains `AND` or `OR` it is sent as-is and entity IDs (including config defaults) are not merged in. |
| `--fields <list>` | string | - | Comma-separated list of fields to return. Sent to the API but not applied by v3 search. |
| `--show-expired` | boolean | false | Include expired memories. |
| `--reference-date <date>` | string | - | Reference date for relative queries (YYYY-MM-DD or unix timestamp). |
| `--latest-only` | boolean | false | Only return the latest version of each memory. |
| `-o, --output <fmt>` | string | `text` | Output format: `text`, `json`, `table`. |

**Examples:**
```bash
mem0 search "preferences" --user-id alice
mem0 search "tools" -u alice -o json -k 5
mem0 search "dietary restrictions" -u alice --threshold 0.5
mem0 search "project setup" -u alice --rerank
mem0 search "preferences" -u alice --filter '{"categories":{"contains":"food"}}'
mem0 search "invoices" -u alice --filter '{"AND":[{"user_id":"alice"},{"categories":{"in":["work"]}}]}'
mem0 search "plans" -u alice --latest-only
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
| `--show-expired` | boolean | false | Include expired memories. |
| `--latest-only` | boolean | false | Only return the latest version of each memory. |
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
| `text` | string | No | New memory text. Falls back to stdin if piped or redirected (Python skips this in `--json`/`--agent` mode; Node does not). |

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-m, --metadata <json>` | string | - | Update metadata as JSON object. |
| `--expires <date>` | string | - | Expiration date (YYYY-MM-DD). Must be in the future. |
| `--timestamp <unix>` | integer | - | Unix timestamp for the memory. |
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
| `--dry-run` | boolean | false | Show what would be deleted without actually deleting. Ignored by `--all --project`, which deletes (see Dry-run behavior). |
| `--force` | boolean | false | Skip confirmation prompt (`--all` and `--entity` only). Required for those modes in `--json`/`--agent` mode. |
| `--delete-linked` | boolean | false | Single-memory mode: also delete memories linked to this memory. |
| `-u, --user-id <id>` | string | - | Scope to user. |
| `--agent-id <id>` | string | - | Scope to agent. |
| `--app-id <id>` | string | - | Scope to app. |
| `--run-id <id>` | string | - | Scope to run. |
| `-o, --output <fmt>` | string | `text` | Output format: `text`, `json`, `quiet`. |

**Three modes (mutually exclusive):**

1. **Single memory:** `mem0 delete <memory_id>` -- deletes one memory by its UUID.
2. **Bulk delete:** `mem0 delete --all [scope flags]` -- deletes all memories matching the scope. Add `--project` to wipe all memories project-wide (sends wildcard `*` entity IDs).
3. **Entity cascade:** `mem0 delete --entity [scope flags]` -- deletes the entity itself AND all its memories.

You cannot combine `<memory_id>` with `--all` or `--entity`, and you cannot combine `--all` with `--entity`. If none of these are provided, the command prints an error and exits 1.

**Entity IDs:** `--all` resolves IDs like `search` (explicit flags only, else config defaults). Single delete and `--entity` use only explicit flags, and `--entity` requires at least one.

**Dry-run behavior:**
- Single: fetches the memory, displays it, and prints "No changes made." (Python: "No changes made (dry run)."). Node also prints "Would delete memory <id8>: <text>".
- `--all`: lists matching memories, prints "Would delete N memories." and the "No changes made" line. In `--json`/`--agent` mode `--all` still requires `--force` even with `--dry-run`, and the command then exits 0 with no output and deletes nothing. Use text mode to see the preview.
- `--entity`: prints "Would delete entity <scope> and all its memories." and the "No changes made" line.
- **Warning:** `--all --project` does not honor `--dry-run`. It skips the preview and deletes every memory in the project (after the confirmation, or immediately with `--force`). Never pass `--dry-run` to `--all --project` expecting a preview. This is a known CLI bug in both CLIs, not intended behavior, so do not rely on it. To preview, run `mem0 delete --all --dry-run` per scope (for example `-u alice`) instead.

**Confirmation:** Without `--force`, `--all` and `--entity` prompt `[y/N]`. Single-memory delete never prompts and ignores `--force`. With `--all --project`, the prompt explicitly warns about project-wide deletion and the scope flags are ignored.

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

**File format:** A JSON array (or single object) where each item has a `memory`, `text`, or `content` field for the text, plus optional `user_id`, `agent_id`, and `metadata` fields. `--user-id` and `--agent-id` override per-item values, and so do the config defaults when neither flag is given. Items with no text count as failed.

**Import format example:**
```json
[
  { "memory": "Prefers dark mode", "user_id": "alice" },
  { "text": "Allergic to nuts", "metadata": { "source": "intake" } },
  { "content": "Uses VS Code" }
]
```

**Behavior:** Iterates through items, calling the add API for each. Displays progress and reports `added` and `failed` counts on completion (text mode writes the summary to stderr in Python and to stdout in Node). In JSON mode the Python CLI sends progress to stderr and includes `scope` in the envelope; the Node CLI writes the progress line to stdout before the JSON (so `| jq` fails) and omits `scope`. Only `-u`, `--agent-id`, `-o`, `--api-key` and `--base-url` are accepted.

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

**Behavior:** `-o json` (or agent mode) returns the standard envelope with `data` shaped as `{"defaults": {"user_id", "agent_id", "app_id", "run_id"}, "platform": {"api_key", "base_url"}}`. The API key is redacted and unset defaults are `null`.

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

**Valid keys:** `platform.api_key`, `platform.base_url`, `platform.user_email`, `defaults.user_id`, `defaults.agent_id`, `defaults.app_id`, `defaults.run_id`, plus the short forms `api_key`, `base_url`, `user_email`, `user_id`, `agent_id`, `app_id`, `run_id`. Python also resolves any other field path in the config file (e.g. `platform.agent_mode`); Node does not.

An unknown key prints "Unknown config key: <key>" and still exits 0. API key values are always redacted in output. `config get` and `config set` emit a `{key, value}` envelope only in `--json`/`--agent` mode.

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
| `-o, --output <fmt>` | string | `table` | Output format: `table`, `json`. |

**Behavior:** Fetches all events for the project. Displays a table with columns: Event ID (first 8 chars), Type, Status (color-coded), Latency, Created. Status values: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`.

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

When `--json` or `--agent` is passed, data commands (add, search, list, get, update, delete, import, config, entity, event, status) wrap their output in a consistent JSON envelope on stdout:

```json
{
  "status": "success",
  "command": "<command_name>",
  "duration_ms": 245,
  "scope": { "user_id": "alice" },
  "count": 10,
  "data": { ... }
}
```

**Fields:**
- `status`: `"success"` or `"error"`.
- `command`: The command name (e.g. `"search"`, `"add"`, `"list"`).
- `duration_ms`: Elapsed time in milliseconds (optional).
- `scope`: Active entity scope with empty values dropped, omitted if empty (optional).
- `count`: Number of results, where applicable (optional).
- `data`: Command-specific response data (`null` on error).
- `error`: Present only on error envelopes (see below); success envelopes have no `error` key.
- `mem0_notice`: Present when the platform flags an unclaimed Agent Mode account (optional).

**Sanitized data fields per command in agent mode:**

| Command | `data` shape |
|---------|-------------|
| `add` | `[{id, event}]` for synchronous results (`--no-infer`) or `[{status, event_id}]` for PENDING (default) |
| `search` | `[{id, memory, score, created_at, categories, expiration_date}]` |
| `list` | `[{id, memory, created_at, categories, expiration_date}]` |
| `get` | `{id, memory, created_at, updated_at, categories, metadata, expiration_date}` |
| `update` | `{id, memory, expiration_date}` |
| `delete` (single) | `{id, deleted}` |
| `delete --all` | `{deleted}`, with `scope` in the envelope (Node: raw API result) |
| `delete --all --project` | `{deleted, scope: "project"}` (Node: raw API result) |
| `delete --entity` / `entity delete` | `{deleted}` |
| `entity list` | `[{name, type}]` |
| `event list` | `[{id, event_type, status, latency, created_at}]` |
| `event status` | `{id, event_type, status, latency, created_at, updated_at, results}` |
| `status` | `{connected, backend, base_url}` |
| `config show` | `{defaults: {user_id, agent_id, app_id, run_id}, platform: {api_key, base_url}}` (key redacted) |
| `config get` / `config set` | `{key, value}` (agent mode only) |
| `import` | `{added, failed}` |

**`-o json` without agent mode:** `list`, `status`, `import` and `config show` print the same envelope. `add`, `search`, `get`, `update`, `delete` and `entity delete` print the raw API JSON instead. `entity list`, `event list` and `event status` print the envelope in Node and raw JSON in Python.

**Error envelope:**
```json
{
  "status": "error",
  "command": "search",
  "error": "Invalid or expired API key.",
  "data": null
}
```

The `error` text varies by CLI and failure point (for example a 401 after the upfront key check passes returns "Authentication failed. Your API key may be invalid or expired."). Branch on `status`, not on the message.

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

This applies to `add`, `search`, `list`, `delete --all`, and `import` (user and agent IDs only). Single `delete` and `entity delete` use only explicitly passed flags.

---

## Filter Building

For `search` and `list`, entity IDs and additional filters are composed into the API filter structure. `--filter` exists only on `search`; `list` builds its extra filters from `--category`, `--after` and `--before`.

1. If the user provides a pre-built filter via `--filter` containing `AND` or `OR` keys, it is passed through to the API as-is (entity IDs, including config defaults, are not merged in).
2. Otherwise, the CLI builds an array of AND conditions:
   - Each entity ID becomes a condition: `{"user_id": "alice"}`, etc.
   - A `--filter` without `AND`/`OR` contributes each of its top-level keys as a condition.
   - Category filters (`list`): `{"categories": {"contains": "<category>"}}`.
   - Date filters (`list`): one condition `{"created_at": {"gte": "YYYY-MM-DD", "lte": "YYYY-MM-DD"}}`, with only the bounds you passed.
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
| `event list` | - | Y | Y | - | `table` |
| `event status` | Y | Y | - | - | `text` |
| `status` | Y | Y | - | - | `text` |

Agent mode (`--json`/`--agent`) overrides the output format with the JSON envelope for all data commands above (it applies to `config get` and `config set` too). See the envelope section for how `-o json` differs from agent mode.
