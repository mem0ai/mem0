# mem0 CLI SDK Specification

Complete reference for the mem0 CLI. This document is the authoritative guide for any developer or AI agent working on this SDK.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Complete Command Reference](#3-complete-command-reference)
4. [API Endpoints](#4-api-endpoints)
5. [Configuration](#5-configuration)
6. [Key Behavioral Patterns](#6-key-behavioral-patterns)
7. [Output Modes](#7-output-modes)
8. [Agent-Friendly Design Decisions](#8-agent-friendly-design-decisions)
9. [Adding a New Command](#9-adding-a-new-command)
10. [Adding a New Language Implementation](#10-adding-a-new-language-implementation)

---

## 1. Project Overview

### What is mem0 CLI?

mem0 CLI is the official command-line interface for [mem0](https://mem0.ai) -- the memory layer for AI agents. It lets developers and AI agents add, search, list, update, and delete memories via the mem0 Platform API from the terminal.

### Who is it for?

- Developers integrating mem0 into their workflows
- AI agents that need persistent memory (the CLI is designed with `--json`/`--agent` global flags and `help --json` specifically for machine consumption)
- DevOps/CI pipelines that need to manage memories programmatically

### Project Structure

The `cli/` directory provides the mem0 CLI in two languages with a shared specification for behavioral consistency.

| Language   | Directory  | Package Name  | Install Command            |
|------------|------------|---------------|----------------------------|
| TypeScript | `node/`    | `@mem0/cli`   | `npm install -g @mem0/cli` |
| Python     | `python/`  | `mem0-cli`    | `pip install mem0-cli`     |

Both implementations produce a binary named `mem0` and provide **identical CLI behavior** -- same commands, same options, same output formats, same error messages.

### Version

Current version: `0.1.0` (defined in `cli-spec.json`, `node/package.json`, and `python/pyproject.toml`).

### License

Apache-2.0

---

## 2. Architecture

### Directory Layout

```
.
├── cli-spec.json                    # Shared CLI specification (source of truth)
├── README.md                        # CLI README
├── SDK_SPECIFICATION.md             # This file
├── python/
│   ├── pyproject.toml               # Python package config (hatchling build)
│   ├── README.md
│   └── src/mem0_cli/
│       ├── __init__.py              # __version__
│       ├── app.py                   # Main Typer app, command registration, helpers
│       ├── config.py                # Config loading/saving, env var overrides
│       ├── branding.py              # Colors, icons, banner, timed_status, print helpers
│       ├── output.py                # Output formatting (text, json, table, quiet)
│       ├── backend/
│       │   ├── __init__.py          # Re-exports get_backend
│       │   ├── base.py              # Abstract Backend ABC, get_backend factory
│       │   └── platform.py          # PlatformBackend (httpx), error classes
│       └── commands/
│           ├── memory.py            # cmd_add, cmd_search, cmd_get, cmd_list, cmd_update, cmd_delete, cmd_delete_all
│           ├── init_cmd.py          # run_init (interactive wizard)
│           ├── config_cmd.py        # cmd_config_show, cmd_config_get, cmd_config_set
│           ├── entities.py          # cmd_entities_list, cmd_entities_delete
│           ├── events_cmd.py        # cmd_event_list, cmd_event_status
│           └── utils.py             # cmd_status, cmd_version, cmd_import
└── node/
    ├── package.json                 # Node package config (tsup build)
    ├── README.md
    └── src/
        ├── index.ts                 # Main Commander.js app, command registration, helpers
        ├── config.ts                # Config loading/saving, env var overrides
        ├── branding.ts              # Colors, icons, banner, timedStatus, print helpers
        ├── output.ts                # Output formatting (text, json, table, quiet)
        ├── state.ts                 # Agent mode flag (setAgentMode, isAgentMode)
        ├── help.ts                  # Rich-style help formatter (panels, command ordering)
        ├── backend/
        │   ├── index.ts             # Re-exports
        │   ├── base.ts              # Backend interface, error classes, getBackend factory
        │   └── platform.ts          # PlatformBackend (native fetch), _buildFilters
        └── commands/
            ├── memory.ts            # cmdAdd, cmdSearch, cmdGet, cmdList, cmdUpdate, cmdDelete, cmdDeleteAll
            ├── init.ts              # runInit (interactive wizard)
            ├── config.ts            # cmdConfigShow, cmdConfigGet, cmdConfigSet
            ├── entities.ts          # cmdEntitiesList, cmdEntitiesDelete
            ├── events.ts            # cmdEventList, cmdEventStatus
            └── utils.ts             # cmdStatus, cmdVersion, cmdImport
```

### How Both CLIs Mirror Each Other

Every command, option, argument, and behavioral pattern is implemented identically in both CLIs. The shared `cli-spec.json` is the source of truth for:

- All command names, descriptions, and usage strings
- All arguments and options (names, types, defaults, help text, panel grouping)
- API endpoint paths and methods
- Branding constants (colors, icons, logo)
- Config schema (sections, fields, env var mappings)
- Error messages and templates
- Option grouping (Scope, Search, Pagination, Filters, Output, Connection)

### Tech Stacks

| Concern          | Python                              | Node                                    |
|------------------|-------------------------------------|-----------------------------------------|
| CLI framework    | Typer >= 0.9.0                      | Commander.js ^12.0.0                    |
| Rich output      | Rich >= 13.0.0                      | chalk ^5.3.0 + cli-table3 ^0.6.4       |
| Spinners         | Rich Status                         | ora ^8.0.0                              |
| Boxed panels     | Rich Panel                          | boxen ^7.1.0                            |
| HTTP client      | httpx >= 0.24.0                     | Native fetch (Node >= 18)               |
| Build system     | Hatchling                           | tsup ^8.0.0                             |
| Test framework   | pytest >= 7.0                       | vitest ^1.5.0                           |
| Linter           | ruff >= 0.1.0                       | Biome ^1.7.0                            |
| Type checking    | (ruff type checks)                  | TypeScript ^5.4.0                       |
| Min runtime      | Python >= 3.10                      | Node >= 18.0.0                          |
| Module format    | Standard Python package              | ESM (`"type": "module"`)               |
| Entrypoint       | `mem0 = "mem0_cli.app:main"`        | `"bin": { "mem0": "./dist/index.js" }`  |

---

## 3. Complete Command Reference

### 3.1 `init`

Interactive setup wizard for mem0 CLI.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 init [OPTIONS]` |
| needsBackend     | No |
| needsConfig      | No |
| resolveIds       | No |
| resolveGraph     | No |
| confirmDangerous | No |

**Options:**

| Flag            | Type   | Required | Default | Help |
|-----------------|--------|----------|---------|------|
| `--api-key`     | string | No       | -       | API key (skip prompt). |
| `-u, --user-id` | string | No       | -       | Default user ID (skip prompt). |
| `--email`       | string | No       | -       | Login via email verification code. |
| `--code`        | string | No       | -       | Verification code (use with --email for non-interactive login). |
| `--force`       | bool   | No       | false   | Overwrite existing config without confirmation. |

**Behavior:**

*Existing config protection:*
- If `~/.mem0/config.json` exists with an API key, the CLI warns and asks for confirmation before overwriting.
- In non-TTY mode, this is a hard error unless `--force` is passed.
- `--force` skips the confirmation in both TTY and non-TTY modes.

*Email login flow (when `--email` is provided):*
- Sends a 6-digit verification code to the email via `POST /api/v1/auth/email_code/`.
- If `--code` is also provided, verifies immediately (fully non-interactive).
- If `--code` is not provided, prompts for the code interactively.
- On success: receives API key, org_id, project_id. Saves to config. Creates account if email is new.
- Cannot be combined with `--api-key`.

*API key flow (existing behavior):*
- If both `--api-key` and `--user-id` are provided, runs non-interactively (no prompts).
- If running in a non-TTY without both flags, prints an error with usage hint and exits.
- Interactive mode: prints banner, prompts for API key (masked with `*`), prompts for default user ID (default: `mem0-cli`), validates connection, saves config.
- API key input uses raw terminal mode to echo `*` for each character typed. Supports backspace and Ctrl+U (clear line).

**Examples:**
```bash
mem0 init
mem0 init --api-key m0-xxx --user-id alice
mem0 init --api-key m0-xxx --user-id alice --force
mem0 init --email alice@company.com
mem0 init --email alice@company.com --code 482901
```

---

### 3.2 `add`

Add a memory from text, messages, file, or stdin.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 add <text> [OPTIONS]` |
| needsBackend     | Yes |
| needsConfig      | Yes |
| resolveIds       | Yes |
| resolveGraph     | Yes |
| confirmDangerous | No |
| Output formats   | text, json, quiet |
| Default output   | text |
| API endpoint     | `POST /v1/memories/` |

**Arguments:**

| Name   | Type   | Required | Help |
|--------|--------|----------|------|
| `text` | string | No       | Text content to add as a memory. |

**Options:**

| Flag             | Type    | Default | Panel      | Help |
|------------------|---------|---------|------------|------|
| `-u, --user-id`  | string  | -       | Scope      | Scope to user. |
| `--agent-id`     | string  | -       | Scope      | Scope to agent. |
| `--app-id`       | string  | -       | Scope      | Scope to app. |
| `--run-id`       | string  | -       | Scope      | Scope to run. |
| `--messages`     | string  | -       | -          | Conversation messages as JSON. |
| `-f, --file`     | path    | -       | -          | Read messages from JSON file. |
| `-m, --metadata` | string  | -       | -          | Custom metadata as JSON. |
| `--immutable`    | boolean | false   | -          | Prevent future updates. |
| `--no-infer`     | boolean | false   | -          | Skip inference, store raw. |
| `--expires`      | string  | -       | -          | Expiration date (YYYY-MM-DD). |
| `--categories`   | string  | -       | -          | Categories (JSON array or comma-separated). |
| `--graph`        | boolean | false   | Scope      | Enable graph memory extraction. |
| `--no-graph`     | boolean | false   | Scope      | Disable graph memory extraction. |
| `-o, --output`   | string  | "text"  | Output     | Output format: text, json, quiet. |
| `--api-key`      | string  | -       | Connection | Override API key. |
| `--base-url`     | string  | -       | Connection | Override API base URL. |

**Input priority:** `--file` > `--messages` > text argument > stdin (if piped and no text).

**Content wrapping:** Text content is wrapped as `[{"role": "user", "content": "<text>"}]` before sending to the API. Messages from `--messages` or `--file` are sent as-is.

**Examples:**
```bash
mem0 add "I prefer dark mode" --user-id alice
echo "text" | mem0 add -u alice
mem0 add --file msgs.json -u alice -o json
```

---

### 3.3 `search`

Search memories by semantic query.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 search <query> [OPTIONS]` |
| needsBackend     | Yes |
| needsConfig      | Yes |
| resolveIds       | Yes |
| resolveGraph     | Yes |
| confirmDangerous | No |
| Output formats   | text, json, table |
| Default output   | text |
| API endpoint     | `POST /v2/memories/search/` |

**Arguments:**

| Name    | Type   | Required | Help |
|---------|--------|----------|------|
| `query` | string | Yes      | Search query. |

**Options:**

| Flag                    | Type    | Default | Panel      | Help |
|-------------------------|---------|---------|------------|------|
| `-u, --user-id`         | string  | -       | Scope      | Filter by user. |
| `--agent-id`            | string  | -       | Scope      | Filter by agent. |
| `--app-id`              | string  | -       | Scope      | Filter by app. |
| `--run-id`              | string  | -       | Scope      | Filter by run. |
| `-k, --top-k, --limit`  | integer | 10      | Search     | Number of results. |
| `--threshold`            | float   | 0.3     | Search     | Minimum similarity score. |
| `--rerank`               | boolean | false   | Search     | Enable reranking (Platform only). |
| `--keyword`              | boolean | false   | Search     | Use keyword search. |
| `--filter`               | string  | -       | Search     | Advanced filter expression (JSON). |
| `--fields`               | string  | -       | Search     | Specific fields to return (comma-separated). |
| `--graph`                | boolean | false   | Search     | Enable graph in search. |
| `--no-graph`             | boolean | false   | Search     | Disable graph in search. |
| `-o, --output`           | string  | "text"  | Output     | Output: text, json, table. |
| `--api-key`              | string  | -       | Connection | Override API key. |
| `--base-url`             | string  | -       | Connection | Override API base URL. |

**Stdin fallback:** If no query argument is provided and stdin is piped, reads query from stdin.

**Examples:**
```bash
mem0 search "preferences" --user-id alice
mem0 search "tools" -u alice -o json -k 5
echo "preferences" | mem0 search -u alice
```

---

### 3.4 `get`

Get a specific memory by ID.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 get <memory_id> [OPTIONS]` |
| needsBackend     | Yes |
| needsConfig      | No |
| resolveIds       | No |
| resolveGraph     | No |
| confirmDangerous | No |
| Output formats   | text, json |
| Default output   | text |
| API endpoint     | `GET /v1/memories/{memory_id}/` |

**Arguments:**

| Name        | Type   | Required | Help |
|-------------|--------|----------|------|
| `memory_id` | string | Yes      | Memory ID to retrieve. |

**Options:**

| Flag           | Type   | Default | Panel      | Help |
|----------------|--------|---------|------------|------|
| `-o, --output` | string | "text"  | Output     | Output: text, json. |
| `--api-key`    | string | -       | Connection | Override API key. |
| `--base-url`   | string | -       | Connection | Override API base URL. |

**Examples:**
```bash
mem0 get abc-123-def-456
mem0 get abc-123-def-456 -o json
```

---

### 3.5 `list`

List memories with optional filters.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 list [OPTIONS]` |
| needsBackend     | Yes |
| needsConfig      | Yes |
| resolveIds       | Yes |
| resolveGraph     | Yes |
| confirmDangerous | No |
| Output formats   | text, json, table |
| Default output   | table |
| API endpoint     | `POST /v2/memories/` |

**Arguments:** None.

**Options:**

| Flag             | Type    | Default | Panel      | Help |
|------------------|---------|---------|------------|------|
| `-u, --user-id`  | string  | -       | Scope      | Filter by user. |
| `--agent-id`     | string  | -       | Scope      | Filter by agent. |
| `--app-id`       | string  | -       | Scope      | Filter by app. |
| `--run-id`       | string  | -       | Scope      | Filter by run. |
| `--page`         | integer | 1       | Pagination | Page number. |
| `--page-size`    | integer | 100     | Pagination | Results per page. |
| `--category`     | string  | -       | Filters    | Filter by category. |
| `--after`        | string  | -       | Filters    | Created after (YYYY-MM-DD). |
| `--before`       | string  | -       | Filters    | Created before (YYYY-MM-DD). |
| `--graph`        | boolean | false   | Filters    | Enable graph in listing. |
| `--no-graph`     | boolean | false   | Filters    | Disable graph in listing. |
| `-o, --output`   | string  | "table" | Output     | Output: text, json, table. |
| `--api-key`      | string  | -       | Connection | Override API key. |
| `--base-url`     | string  | -       | Connection | Override API base URL. |

**Examples:**
```bash
mem0 list -u alice
mem0 list --category prefs --after 2024-01-01 -o json
```

---

### 3.6 `update`

Update a memory's text or metadata.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 update <memory_id> [text] [OPTIONS]` |
| needsBackend     | Yes |
| needsConfig      | No |
| resolveIds       | No |
| resolveGraph     | No |
| confirmDangerous | No |
| Output formats   | text, json, quiet |
| Default output   | text |
| API endpoint     | `PUT /v1/memories/{memory_id}/` |

**Arguments:**

| Name        | Type   | Required | Help |
|-------------|--------|----------|------|
| `memory_id` | string | Yes      | Memory ID to update. |
| `text`      | string | No       | New memory text. |

**Options:**

| Flag             | Type   | Default | Panel      | Help |
|------------------|--------|---------|------------|------|
| `-m, --metadata` | string | -       | -          | Update metadata (JSON). |
| `-o, --output`   | string | "text"  | Output     | Output: text, json, quiet. |
| `--api-key`      | string | -       | Connection | Override API key. |
| `--base-url`     | string | -       | Connection | Override API base URL. |

**Stdin fallback:** If no text argument is provided and no `--metadata` flag is set and stdin is piped, reads text from stdin.

**Examples:**
```bash
mem0 update abc-123 "new text"
mem0 update abc-123 --metadata '{"key":"val"}'
echo "new text" | mem0 update abc-123
```

---

### 3.7 `delete`

Delete a memory, all memories matching a scope, or an entity. This is a consolidated command with three mutually exclusive modes.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 delete [memory_id] [OPTIONS]` |
| needsBackend     | Yes |
| needsConfig      | Yes |
| resolveIds       | Yes |
| resolveGraph     | No |
| confirmDangerous | Yes |
| Output formats   | text, json, quiet |
| Default output   | text |
| API endpoint     | `DELETE /v1/memories/{memory_id}/` (single), `DELETE /v1/memories/` (--all), `DELETE /v1/entities/` (--entity) |

**Arguments:**

| Name        | Type   | Required | Help |
|-------------|--------|----------|------|
| `memory_id` | string | No       | Memory ID to delete (omit when using --all or --entity). |

**Options:**

| Flag            | Type    | Default | Panel      | Help |
|-----------------|---------|---------|------------|------|
| `--all`         | boolean | false   | -          | Delete all memories matching scope filters. |
| `--entity`      | boolean | false   | -          | Delete the entity itself and all its memories (cascade). |
| `--project`     | boolean | false   | -          | With --all: delete ALL memories project-wide. |
| `--dry-run`     | boolean | false   | -          | Show what would be deleted without deleting. |
| `--force`       | boolean | false   | -          | Skip confirmation. |
| `-u, --user-id` | string  | -       | Scope      | Scope to user. |
| `--agent-id`    | string  | -       | Scope      | Scope to agent. |
| `--app-id`      | string  | -       | Scope      | Scope to app. |
| `--run-id`      | string  | -       | Scope      | Scope to run. |
| `-o, --output`  | string  | "text"  | Output     | Output: text, json, quiet. |
| `--api-key`     | string  | -       | Connection | Override API key. |
| `--base-url`    | string  | -       | Connection | Override API base URL. |

**Three modes (mutually exclusive):**

1. **Single memory:** `mem0 delete <memory_id>` -- deletes one memory by ID. Cannot combine with `--all` or `--entity`.
2. **Bulk delete:** `mem0 delete --all [scope]` -- deletes all memories matching scope filters. Use `--project` with `--all` to wipe all memories project-wide (sends wildcard `*` entity IDs). Cannot combine with `<memory_id>` or `--entity`.
3. **Entity cascade:** `mem0 delete --entity [scope]` -- deletes the entity itself and all its memories. Cannot combine with `<memory_id>` or `--all`.

If none of `<memory_id>`, `--all`, or `--entity` is provided, the command prints a usage hint and exits with an error.

**Dry-run behavior:**
- Single: fetches the memory via `GET`, displays it, then prints "No changes made."
- `--all`: lists matching memories and displays the count, then prints "No changes made."
- `--entity`: shows the scope that would be affected without deleting.

**Confirmation:** Without `--force`, prompts the user with "[y/N]" confirmation. With `--all --project`, the prompt warns about entire project wipe.

**`--all --project` wildcard behavior:** Sends `DELETE /v1/memories/` with query params `user_id=*&agent_id=*&app_id=*&run_id=*`. The API typically returns an async response with a `message` field (deletion happens in background). The CLI detects this and prints "Deletion started. Memories will be removed in the background."

**Examples:**
```bash
mem0 delete abc-123-def-456              # single memory
mem0 delete --all -u alice --force        # all memories for user
mem0 delete --all --project --force       # project-wide wipe
mem0 delete --entity -u alice --force     # entity + all its memories
mem0 delete abc-123 --dry-run             # preview single delete
```

---

### 3.8 `import`

Import memories from a JSON file.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 import <file_path> [OPTIONS]` |
| needsBackend     | Yes |
| needsConfig      | Yes |
| resolveIds       | Yes |
| resolveGraph     | No |
| confirmDangerous | No |
| Output formats   | text, json |
| Default output   | text |
| API endpoint     | `POST /v1/memories/` (per item) |

**Arguments:**

| Name        | Type   | Required | Help |
|-------------|--------|----------|------|
| `file_path` | string | Yes      | JSON file to import. |

**Options:**

| Flag            | Type   | Default | Panel      | Help |
|-----------------|--------|---------|------------|------|
| `-u, --user-id` | string | -       | Scope      | Override user ID. |
| `--agent-id`    | string | -       | Scope      | Override agent ID. |
| `-o, --output`  | string | "text"  | Output     | Output: text, json. |
| `--api-key`     | string | -       | Connection | Override API key. |
| `--base-url`    | string | -       | Connection | Override API base URL. |

**File format:** JSON array (or single object) where each item has `memory`, `text`, or `content` field for the text, plus optional `user_id`, `agent_id`, and `metadata` fields.

**Behavior:** Iterates through items, calling `backend.add()` for each. CLI-provided `--user-id` and `--agent-id` override per-item values. Displays progress indicator (every 10 items in Node, Rich progress bar in Python). Reports `added` and `failed` counts.

**JSON output envelope:**
```json
{
  "status": "success",
  "command": "import",
  "data": { "added": 42, "failed": 0, "duration_s": 3.14 },
  "duration_ms": 3140
}
```

**Examples:**
```bash
mem0 import data.json --user-id alice
mem0 import data.json -u alice -o json
```

---

### 3.9 `config show`

Display current configuration (secrets redacted).

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 config show [OPTIONS]` |
| needsBackend     | No |
| needsConfig      | No |

**Options:**

| Flag           | Type   | Default | Help |
|----------------|--------|---------|------|
| `-o, --output` | string | "text"  | Output: text, json. |

**Behavior:** Loads config (file + env vars), displays as table (text) or JSON envelope. API keys are always redacted using `redact_key()`.

**Examples:**
```bash
mem0 config show
mem0 config show -o json
```

---

### 3.10 `config get`

Get a configuration value.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 config get <key>` |
| needsBackend     | No |
| needsConfig      | No |

**Arguments:**

| Name  | Type   | Required | Help |
|-------|--------|----------|------|
| `key` | string | Yes      | Config key (e.g. `platform.api_key`). |

**Valid keys:** `platform.api_key`, `platform.base_url`, `defaults.user_id`, `defaults.agent_id`, `defaults.app_id`, `defaults.run_id`, `defaults.enable_graph`.

**Behavior:** Prints the value to stdout. API keys are redacted. Unknown keys print an error.

**Examples:**
```bash
mem0 config get platform.api_key
mem0 config get defaults.user_id
```

---

### 3.11 `config set`

Set a configuration value.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 config set <key> <value>` |
| needsBackend     | No |
| needsConfig      | No |

**Arguments:**

| Name    | Type   | Required | Help |
|---------|--------|----------|------|
| `key`   | string | Yes      | Config key (e.g. `platform.api_key`). |
| `value` | string | Yes      | Value to set. |

**Type coercion:** Boolean fields accept `true/1/yes` (case-insensitive) as true, anything else as false. Integer fields are parsed via `parseInt`. String fields are stored as-is.

**Examples:**
```bash
mem0 config set defaults.user_id alice
mem0 config set platform.base_url https://api.mem0.ai
```

---

### 3.12 `entity list`

List all entities of a given type.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 entity list <entity_type>` |
| needsBackend     | Yes |
| needsConfig      | No |
| resolveIds       | No |
| resolveGraph     | No |
| confirmDangerous | No |
| Output formats   | table, json |
| Default output   | table |
| API endpoint     | `GET /v1/entities/` |

**Arguments:**

| Name          | Type   | Required | Choices                        | Help |
|---------------|--------|----------|--------------------------------|------|
| `entity_type` | string | Yes      | `users`, `agents`, `apps`, `runs` | Entity type to list. |

**Behavior:** Calls `GET /v1/entities/` which returns ALL entity types, then filters client-side using the type map: `users` -> `user`, `agents` -> `agent`, `apps` -> `app`, `runs` -> `run`. Displays a table with "Name / ID" and "Created" columns.

**Options:**

| Flag           | Type   | Default | Panel      | Help |
|----------------|--------|---------|------------|------|
| `-o, --output` | string | "table" | Output     | Output: table, json. |
| `--api-key`    | string | -       | Connection | Override API key. |
| `--base-url`   | string | -       | Connection | Override API base URL. |

**Examples:**
```bash
mem0 entity list users
mem0 entity list agents -o json
```

---

### 3.13 `entity delete`

Delete an entity and ALL its memories (cascade). Also accessible via `mem0 delete --entity`.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 entity delete [OPTIONS]` |
| needsBackend     | Yes |
| needsConfig      | No |
| resolveIds       | No |
| resolveGraph     | No |
| confirmDangerous | Yes |
| Output formats   | text, json, quiet |
| Default output   | text |
| API endpoint     | `DELETE /v1/entities/` |

**Arguments:** None.

**Options:**

| Flag            | Type    | Default | Panel      | Help |
|-----------------|---------|---------|------------|------|
| `-u, --user-id` | string  | -       | Scope      | User ID. |
| `--agent-id`    | string  | -       | Scope      | Agent ID. |
| `--app-id`      | string  | -       | Scope      | App ID. |
| `--run-id`      | string  | -       | Scope      | Run ID. |
| `--dry-run`     | boolean | false   | -          | Show what would be deleted without deleting. |
| `--force`       | boolean | false   | -          | Skip confirmation. |
| `-o, --output`  | string  | "text"  | Output     | Output: text, json, quiet. |
| `--api-key`     | string  | -       | Connection | Override API key. |
| `--base-url`    | string  | -       | Connection | Override API base URL. |

**Validation:** At least one entity ID is required. Errors if none provided.

**Examples:**
```bash
mem0 entity delete --user-id alice --force
mem0 entity delete --user-id alice --dry-run
```

---

### 3.14 `event list`

List recent background processing events.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 event list [OPTIONS]` |
| needsBackend     | Yes |
| needsConfig      | Yes |
| resolveIds       | No |
| resolveGraph     | No |
| confirmDangerous | No |
| Output formats   | text (table), json |
| Default output   | table |
| API endpoint     | `GET /v1/events/` |

**Options:**

| Flag           | Type   | Default | Panel      | Help |
|----------------|--------|---------|------------|------|
| `-o, --output` | string | "table" | Output     | Output: text, json. |
| `--api-key`    | string | -       | Connection | Override API key. |
| `--base-url`   | string | -       | Connection | Override API base URL. |

**Behavior:** Fetches all background events for the project. Displays as a table with columns: Event ID (first 8 chars), Type, Status (color-coded), Latency, Created. Status values: `PENDING` (accent), `SUCCEEDED` (green), `FAILED` (red), `PROCESSING` (yellow).

**JSON output envelope:**
```json
{
  "status": "success",
  "command": "event list",
  "count": 3,
  "duration_ms": 87,
  "data": [
    { "id": "evt-abc", "event_type": "ADD", "status": "SUCCEEDED", "latency": 412.0, "created_at": "2026-01-01T10:00:00Z" }
  ]
}
```

**Examples:**
```bash
mem0 event list
mem0 event list --output json
```

---

### 3.15 `event status`

Get the status and results of a specific background event.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 event status <event_id> [OPTIONS]` |
| needsBackend     | Yes |
| needsConfig      | Yes |
| resolveIds       | No |
| resolveGraph     | No |
| confirmDangerous | No |
| Output formats   | text, json |
| Default output   | text |
| API endpoint     | `GET /v1/events/{event_id}/` |

**Arguments:**

| Name       | Type   | Required | Help |
|------------|--------|----------|------|
| `event_id` | string | Yes      | Event ID to inspect. |

**Options:**

| Flag           | Type   | Default | Panel      | Help |
|----------------|--------|---------|------------|------|
| `-o, --output` | string | "text"  | Output     | Output: text, json. |
| `--api-key`    | string | -       | Connection | Override API key. |
| `--base-url`   | string | -       | Connection | Override API base URL. |

**Behavior:** Fetches the event by ID and displays: Event ID, Type, Status (color-coded), Latency, Created, Updated, and a numbered list of result memories (event type, memory text, user_id, truncated memory ID). Displayed in a boxed panel (text) or JSON envelope.

**JSON output envelope:**
```json
{
  "status": "success",
  "command": "event status",
  "duration_ms": 65,
  "data": {
    "id": "evt-abc",
    "event_type": "ADD",
    "status": "SUCCEEDED",
    "latency": 412.0,
    "created_at": "2026-01-01T10:00:00Z",
    "updated_at": "2026-01-01T10:00:01Z",
    "results": [
      { "id": "mem-xyz", "event": "ADD", "user_id": "alice", "memory": "User prefers dark mode" }
    ]
  }
}
```

**Examples:**
```bash
mem0 event status evt-abc-123
mem0 event status evt-abc-123 --output json
```

---

### 3.16 `status`

Check connectivity and authentication.

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 status [OPTIONS]` |
| needsBackend     | Yes |
| needsConfig      | Yes |
| resolveIds       | No |
| resolveGraph     | No |
| confirmDangerous | No |

**Options:**

| Flag           | Type   | Default | Panel      | Help |
|----------------|--------|---------|------------|------|
| `-o, --output` | string | "text"  | Output     | Output: text, json. |
| `--api-key`    | string | -       | Connection | Override API key. |
| `--base-url`   | string | -       | Connection | Override API base URL. |

**Behavior:** Validates connectivity by calling `GET /v1/ping/`. Displays connection status in a boxed panel (text) or JSON envelope. The ping endpoint is lightweight and does not require any entity scope.

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

### 3.17 `help`

Show help. Use `--json` for machine-readable output (for LLM agents).

| Property         | Value |
|------------------|-------|
| Usage            | `mem0 help [OPTIONS]` |
| needsBackend     | No |
| needsConfig      | No |

**Options:**

| Flag     | Type    | Default | Help |
|----------|---------|---------|------|
| `--json` | boolean | false   | Output machine-readable JSON for LLM agents. |

**Behavior:**
- Without `--json`: prints a human-readable summary of all commands.
- With `--json`: Node outputs the entire `cli-spec.json` file. Python outputs a hand-built JSON object describing all commands, arguments, options, and global options.

**Examples:**
```bash
mem0 help
mem0 help --json
```

---

## 4. API Endpoints

### Base URL

Default: `https://api.mem0.ai` (configurable via `--base-url`, `MEM0_BASE_URL`, or `platform.base_url` in config).

### Authentication

All requests include the header:
```
Authorization: Token <api_key>
```

The auth header name is `Authorization` and the scheme is `Token` (not Bearer).

### Timeout

30 seconds for all requests (Python: `httpx.Client(timeout=30.0)`, Node: `AbortSignal.timeout(30_000)`).

### Endpoint Reference

| Operation       | Method   | Path                          | Request Body     | Query Params            |
|-----------------|----------|-------------------------------|------------------|-------------------------|
| Add memory      | `POST`   | `/v1/memories/`               | JSON payload     | -                       |
| Search          | `POST`   | `/v2/memories/search/`        | JSON payload     | -                       |
| Get memory      | `GET`    | `/v1/memories/{memory_id}/`   | -                | -                       |
| List memories   | `POST`   | `/v2/memories/`               | JSON payload     | `page`, `page_size`     |
| Update memory   | `PUT`    | `/v1/memories/{memory_id}/`   | JSON payload     | -                       |
| Delete memory   | `DELETE` | `/v1/memories/{memory_id}/`   | -                | -                       |
| Delete all      | `DELETE` | `/v1/memories/`               | -                | entity ID params        |
| List entities   | `GET`    | `/v1/entities/`               | -                | -                       |
| Delete entities | `DELETE` | `/v1/entities/`               | -                | entity ID params        |
| List events     | `GET`    | `/v1/events/`                 | -                | -                       |
| Get event       | `GET`    | `/v1/events/{event_id}/`      | -                | -                       |
| Ping (status)   | `GET`    | `/v1/ping/`                   | -                | -                       |

### How Filters Are Built (`_buildFilters` / `_build_filters`)

Both CLIs use an identical filter-building algorithm:

1. If the caller passed a pre-built filter structure containing `AND` or `OR` keys (e.g. from `--filter`), use it directly.
2. Otherwise, build an array of AND conditions:
   - Each entity ID becomes `{"user_id": "..."}`, `{"agent_id": "..."}`, etc.
   - Extra filters (category, date ranges) are appended as additional conditions.
3. If exactly 1 condition: return it directly (no wrapping).
4. If 2+ conditions: return `{"AND": [condition1, condition2, ...]}`.
5. If 0 conditions: return `undefined`/`None`.

**Category filter format:** `{"categories": {"contains": "<category>"}}`

**Date filter format:** `{"created_at": {"gte": "YYYY-MM-DD"}}` and/or `{"created_at": {"lte": "YYYY-MM-DD"}}`. If both `after` and `before` are set, they merge into one `created_at` object: `{"created_at": {"gte": "...", "lte": "..."}}`.

### How Pagination Works

For the `list` command (and `search` internally):
- `page` and `page_size` are sent as **query parameters** (not in the POST body).
- Filters and `enable_graph` are sent in the **POST body**.
- Default: `page=1`, `page_size=100`.

### Response Normalization

Both CLIs handle inconsistent API response formats:
```
# For search and list, the API may return:
result = [...]              # Direct array
result = {"results": [...]} # Wrapped in results key
result = {"memories": [...]} # Wrapped in memories key

# Normalization logic (identical in both CLIs):
if isinstance(result, list):
    return result
else:
    return result.get("results", result.get("memories", []))
```

### Error Handling

HTTP errors are mapped to typed exceptions:

| HTTP Status | Error Class    | Message Template |
|-------------|----------------|-----------------|
| 401         | `AuthError`    | "Authentication failed. Your API key may be invalid or expired." |
| 404         | `NotFoundError`| "Resource not found: {path}" |
| 400         | `APIError`     | "Bad request to {path}: {detail}" (detail extracted from response JSON `.detail` field) |
| 204         | (success)      | Returns `{}` (empty object) |
| Other       | Generic Error  | "HTTP {status}: {statusText}" |

---

## 5. Configuration

### Config File Location

- Directory: `~/.mem0/` (created with permissions `0700`)
- File: `~/.mem0/config.json` (written with permissions `0600`)

### Config Precedence (highest to lowest)

1. **CLI flags** (`--api-key`, `--base-url`, `--user-id`, etc.)
2. **Environment variables** (`MEM0_API_KEY`, etc.)
3. **Config file** (`~/.mem0/config.json`)
4. **Defaults** (hardcoded)

### Environment Variables

| Variable           | Config Path              | Type    | Default               |
|--------------------|--------------------------|---------|-----------------------|
| `MEM0_API_KEY`     | `platform.api_key`       | string  | `""`                  |
| `MEM0_BASE_URL`    | `platform.base_url`      | string  | `"https://api.mem0.ai"` |
| `MEM0_USER_ID`     | `defaults.user_id`       | string  | `""`                  |
| `MEM0_AGENT_ID`    | `defaults.agent_id`      | string  | `""`                  |
| `MEM0_APP_ID`      | `defaults.app_id`        | string  | `""`                  |
| `MEM0_RUN_ID`      | `defaults.run_id`        | string  | `""`                  |
| `MEM0_ENABLE_GRAPH`| `defaults.enable_graph`  | boolean | `false`               |

**Boolean parsing for `MEM0_ENABLE_GRAPH`:** Accepted truthy values are `"true"`, `"1"`, `"yes"` (case-insensitive). Everything else is `false`.

### Config File JSON Schema

```json
{
  "version": 1,
  "defaults": {
    "user_id": "",
    "agent_id": "",
    "app_id": "",
    "run_id": "",
    "enable_graph": false
  },
  "platform": {
    "api_key": "",
    "base_url": "https://api.mem0.ai"
  }
}
```

| Field                    | Type    | Default                  | Description |
|--------------------------|---------|--------------------------|-------------|
| `version`                | integer | `1`                      | Config schema version. |
| `defaults.user_id`       | string  | `""`                     | Default user ID for scoping. |
| `defaults.agent_id`      | string  | `""`                     | Default agent ID for scoping. |
| `defaults.app_id`        | string  | `""`                     | Default app ID for scoping. |
| `defaults.run_id`        | string  | `""`                     | Default run ID for scoping. |
| `defaults.enable_graph`  | boolean | `false`                  | Default graph memory extraction. |
| `platform.api_key`       | string  | `""`                     | API key for mem0 Platform. |
| `platform.base_url`      | string  | `"https://api.mem0.ai"`  | Base URL for API requests. |

### Config Key Map (for `config get`/`config set`)

The dotted key paths map to internal config objects as follows:

| Dotted Key              | Section    | Field        |
|-------------------------|------------|--------------|
| `platform.api_key`      | platform   | apiKey / api_key |
| `platform.base_url`     | platform   | baseUrl / base_url |
| `defaults.user_id`      | defaults   | userId / user_id |
| `defaults.agent_id`     | defaults   | agentId / agent_id |
| `defaults.app_id`       | defaults   | appId / app_id |
| `defaults.run_id`       | defaults   | runId / run_id |
| `defaults.enable_graph` | defaults   | enableGraph / enable_graph |

### API Key Redaction

The `redact_key`/`redactKey` function:
- Empty string: returns `"(not set)"`
- Length <= 8: returns first 2 chars + `"***"`
- Length > 8: returns first 4 chars + `"..."` + last 4 chars

---

## 6. Key Behavioral Patterns

These patterns are the **contract** both CLIs must follow. Any new implementation must replicate them exactly.

### 6.1 Entity ID Resolution

**Function:** `_resolve_ids` (Python) / `resolveIds` (Node)

**Rule:** If **any** explicit entity ID is provided via CLI flags, only use the explicitly provided IDs. Do NOT mix in defaults for other entity types (which would over-filter). If **no** explicit IDs are provided, fall back to **all** configured defaults.

```
if any(user_id, agent_id, app_id, run_id):
    # Only use what was explicitly passed; others become None
    return {user_id or None, agent_id or None, app_id or None, run_id or None}
else:
    # Fall back to all configured defaults
    return {config.user_id or None, config.agent_id or None, ...}
```

**Rationale:** If a user passes `--user-id alice` and the config also has `agent_id=bot1`, they probably want only Alice's memories, not the intersection of Alice AND bot1.

### 6.2 Graph Tri-State Resolution

**Rule:** `--no-graph` > `--graph` > config default.

```
if opts.no_graph: return false
if opts.graph: return true
return config.defaults.enable_graph
```

This is resolved in the main app file (not in the command handlers) before calling the command function.

### 6.3 Category Parsing

**Rule:** Try JSON parse first, fallback to comma-split.

```
if categories:
    try:
        cats = JSON.parse(categories)  # e.g. '["a","b"]'
    except:
        cats = categories.split(",").map(s => s.trim())  # e.g. "a, b"
```

### 6.4 Stdin Detection

**Rule:** Read from stdin if no text argument is provided AND stdin is piped (not a TTY).

- `add`: If no `text`, no `--messages`, no `--file`, and stdin is piped -> read content from stdin.
- `search`: If no `query` argument and stdin is piped -> read query from stdin.
- `update`: If no `text` argument and no `--metadata` and stdin is piped -> read text from stdin.

Detection method:
- Python: `not sys.stdin.isatty()`
- Node: `!process.stdin.isTTY`

Reading method:
- Python: `sys.stdin.read().strip()`
- Node: `fs.readFileSync(0, "utf-8").trim()`

### 6.5 Filter Building (`_buildFilters`)

Detailed algorithm (see Section 4 for full description):

1. If `extraFilters` has `AND` or `OR` key -> return it as-is (pre-built filter).
2. Collect AND conditions from entity IDs.
3. Append extra filters (category, date ranges).
4. 0 conditions -> `undefined`/`None`.
5. 1 condition -> return that single object.
6. 2+ conditions -> `{"AND": [...]}`.

### 6.6 API Response Normalization

All `search` and `listMemories`/`list_memories` calls normalize the response:

```
if Array.isArray(result): return result
return result.results ?? result.memories ?? []
```

This handles both direct array responses and wrapped `{results: [...]}` or `{memories: [...]}` formats.

### 6.7 Config File Permissions

- Config directory (`~/.mem0/`): created with mode `0o700` (owner read+write+execute only).
- Config file (`~/.mem0/config.json`): written with mode `0o600` (owner read+write only).
- Python uses `os.chmod()` with `stat.S_IRWXU` (dir) and `stat.S_IRUSR | stat.S_IWUSR` (file).
- Node uses `fs.mkdirSync(..., { mode: 0o700 })` and `fs.chmodSync(file, 0o600)`.

### 6.8 Timed Status Pattern

Every API call is wrapped in a spinner + timing pattern:

**Python:**
```python
with timed_status(err_console, "Adding memory...") as ts:
    result = backend.add(...)
```
Uses Rich `Status` context manager on stderr. On success, prints `ts.success_msg` with elapsed time. On error, prints `ts.error_msg` with elapsed time.

**Node:**
```typescript
result = await timedStatus("Adding memory...", async (ctx) => {
    return backend.add(...);
});
```
Uses `ora` spinner on stderr. On success, prints `ctx.successMsg` with elapsed time. On error, prints `ctx.errorMsg` with elapsed time.

Both use `performance.now()` / `time.perf_counter()` for timing. Elapsed time is formatted as `{seconds:.2f}s`.

**Key:** Spinners and timing messages always go to **stderr** so they never contaminate machine-readable stdout.

### 6.9 Error Hierarchy

```
AuthError    (HTTP 401) -> "Authentication failed. Your API key may be invalid or expired."
NotFoundError (HTTP 404) -> "Resource not found: {path}"
APIError     (HTTP 400) -> "Bad request to {path}: {detail}"
```

For HTTP 400, the CLI attempts to extract a `detail` field from the JSON response body. If parsing fails, falls back to `resp.statusText`/`resp.text`.

HTTP 204 is treated as success with empty body (`{}`).

Any other non-OK response throws a generic error with `"HTTP {status}: {statusText}"`.

### 6.10 `delete --all --project` Wildcard Behavior

When `delete --all --project` is used, the CLI sends wildcard entity IDs (`user_id=*`, `agent_id=*`, `app_id=*`, `run_id=*`) to `DELETE /v1/memories/`. The API typically returns an **asynchronous response** with a `message` field (the deletion happens in the background). The CLI detects the `message` key in the response and prints "Deletion started. Memories will be removed in the background." instead of a success count.

### 6.11 Non-Interactive Init

When both `--api-key` and `--user-id` are provided to `mem0 init`:
1. Sets config values directly (no prompts).
2. Validates the platform connection.
3. Saves config to disk.
4. Prints success message.

When running in a non-TTY (piped input) without both flags, prints an error with usage hint:
```
"Non-interactive terminal detected and missing required flags."
"Usage: mem0 init --api-key <key> --user-id <id>"
```

### 6.12 Add Result Event Display

The `format_add_result` function handles the API response from `POST /v1/memories/`:

The response is either a direct array or `{results: [...]}`. Each result item has an `event` field:

| Event    | Icon | Label      |
|----------|------|------------|
| `ADD`    | `+`  | Added      |
| `UPDATE` | `~`  | Updated    |
| `DELETE` | `-`  | Deleted    |
| `NOOP`   | `.`  | No change  |
| `PENDING`| hourglass | Queued (async) |

For `PENDING` events, displays "Processing in background" with the event ID.

---

## 7. Output Modes

### 7.1 Supported Modes Per Command

All commands also support `agent` mode via the global `--json`/`--agent` flag, which wraps output in a structured JSON envelope with sanitized fields.

| Command        | text | json | table | quiet |
|----------------|------|------|-------|-------|
| add            | Y    | Y    | -     | Y     |
| search         | Y    | Y    | Y     | -     |
| get            | Y    | Y    | -     | -     |
| list           | Y    | Y    | Y (default) | -  |
| update         | Y    | Y    | -     | Y     |
| delete         | Y    | Y    | -     | Y     |
| import         | Y    | Y    | -     | -     |
| config show    | Y    | Y    | -     | -     |
| config get     | (raw value) | - | - | -    |
| config set     | (success msg) | - | - | -  |
| entity list    | -    | Y    | Y (default) | -  |
| entity delete  | Y    | Y    | -     | Y     |
| event list     | Y (table) | Y | -  | -     |
| event status   | Y    | Y    | -     | -     |
| status         | Y    | Y    | -     | -     |
| help           | Y    | Y (--json) | - | -   |

### 7.2 JSON Envelope Format

There are two related envelope formats:

**`formatJsonEnvelope`** — used by `config show`, `status`, and `import` for `--output json`:

```json
{
  "status": "success",
  "command": "<command_name>",
  "duration_ms": 245,
  "scope": {"user_id": "alice", "agent_id": null},
  "count": 10,
  "error": null,
  "data": { ... }
}
```

**`formatAgentEnvelope`** — used by all commands in agent mode (`--json`/`--agent`). Same structure, but `data` is passed through `sanitizeAgentData(command, data)` to project only the most relevant fields:

| Command       | Fields in `data` |
|---------------|-----------------|
| add           | `[{id, memory, event}]` or `[{status, event_id}]` for PENDING |
| search        | `[{id, memory, score, created_at, categories}]` |
| list          | `[{id, memory, created_at, categories}]` |
| get           | `{id, memory, created_at, updated_at, categories, metadata}` |
| update        | `{id, memory}` |
| delete        | (raw API response) |
| entity list   | `[{name, type, count}]` |
| event list    | `[{id, event_type, status, latency, created_at}]` |
| event status  | `{id, event_type, status, latency, created_at, updated_at, results: [{id, event, user_id, memory}]}` |
| status/config/import | (pass-through) |

Error envelopes (on non-zero exit):
```json
{
  "status": "error",
  "command": "<command_name>",
  "error": "Authentication failed. Your API key may be invalid or expired.",
  "data": null
}
```

Fields:
- `status`: `"success"` or `"error"`.
- `command`: The command name.
- `duration_ms`: Optional, elapsed time in milliseconds.
- `scope`: Optional, active entity scope (omitted if empty).
- `count`: Optional, result count.
- `error`: Only present when `status` is `"error"`.
- `data`: The primary payload (sanitized in agent mode).

### 7.3 Text Output

- `formatMemoriesText`: Numbered list with memory text, score, ID (first 8 chars), created date, and category, separated by ` . ` in dim color.
- `formatSingleMemory`: Boxed panel (boxen/Rich Panel) showing memory text, ID, created date, updated date, metadata, and categories.
- `formatAddResult`: Event-based output with icons (+, ~, -, .) and labels.

### 7.4 Table Output

Uses `cli-table3` (Node) or `rich.table.Table` (Python) with columns:
- ID (first 8 chars, dim)
- Memory (truncated to 60 chars with "...")
- Category (first category from array)
- Created (YYYY-MM-DD)

### 7.5 Quiet Mode

Commands that support `--output quiet` (`add`, `update`, `delete`, `entity delete`) produce **no stdout output** in quiet mode. The operation still executes. Exit code indicates success/failure.

### 7.6 Error Output

- **Errors always go to stderr.** Both CLIs use a separate stderr console:
  - Python: `Console(stderr=True)` for `print_error` calls.
  - Node: `console.error()` in `printError`, spinner on `process.stderr` stream.
- **Data always goes to stdout.** JSON output, table output, and text output all go to stdout.

### 7.7 Unicode Symbol Degradation

The `_sym`/`sym` function selects symbols based on terminal capability:

| Condition                              | Fancy Symbol | Plain Fallback |
|----------------------------------------|-------------|----------------|
| `!stdout.isTTY` or `NO_COLOR` env set | -           | Used           |
| Interactive TTY with color             | Used        | -              |

| Symbol   | Fancy | Plain     |
|----------|-------|-----------|
| Success  | `checkmark` | `[ok]`    |
| Error    | `X`   | `[error]` |
| Warning  | `warning triangle` | `[warn]`  |
| Info     | `diamond` | `*`       |

### 7.8 Result Summary Footer

After list/search results, a summary line is printed in dim:
```
  10 results . page 1 . user id=alice . 0.45s
```

Format: `{count} result(s) . page {n} . {scope} . {elapsed}s`

### 7.9 Date Formatting

All dates are normalized to `YYYY-MM-DD` format for display. The formatting handles ISO 8601 strings with `Z` timezone suffix by replacing it with `+00:00` before parsing.

---

## 8. Agent-Friendly Design Decisions

### Why `--dry-run` exists on destructive commands

The `delete` command (all modes) and `entity delete` support `--dry-run`. This lets AI agents preview the effect of a destructive operation before committing. For `delete <id>`, it fetches the memory and displays it. For `delete --all`, it lists matching memories and shows the count. For `delete --entity` / `entity delete`, it shows the scope that would be affected.

### Why `--force` exists

Destructive commands (`delete --all`, `delete --entity`, `entity delete`) require interactive confirmation by default. The `--force` flag skips this confirmation, which is essential for:
- AI agents (non-interactive)
- CI/CD pipelines
- Scripting

### Why `--json`/`--agent` global flags exist

The `--json` and `--agent` flags (aliases of each other) activate agent mode globally. When set:
1. All output becomes a structured JSON envelope (`{status, command, duration_ms, scope, count, data}`).
2. The `data` field is sanitized via `sanitizeAgentData` — only the most relevant fields are included per command, reducing noise for agents parsing the output.
3. All human-readable output (spinners, colors, banners, timing lines) is suppressed.
4. Errors are emitted as JSON to stdout with a non-zero exit code, not to stderr as text.

This is distinct from `--output json`, which returns the raw API response without sanitization.

### Why `--output json` is on every command

Every data-returning command supports `--output json` (or `--json` for `help`). This enables machine consumption by AI agents and scripts. JSON output goes to stdout while human-readable spinners/timing go to stderr, so piping `mem0 list -o json | jq .` works cleanly.

### Why stdin is supported

Commands `add`, `search`, and `update` can read from stdin when piped. This enables composability:
```bash
echo "I prefer dark mode" | mem0 add -u alice
cat query.txt | mem0 search -u alice
echo "updated text" | mem0 update abc-123
```

### Why `help --json` exists

The `help --json` command outputs the complete CLI specification in machine-readable JSON. AI agents can call this once to discover all available commands, their arguments, options, and valid values -- enabling self-documenting tool use.

### Why errors go to stderr

All error messages, warnings, spinners, and timing information go to stderr. This means `--output json` produces **only** valid JSON on stdout, with no interleaved human-readable messages. An AI agent can safely parse stdout as JSON.

---

## 9. Adding a New Command

Step-by-step guide for adding a new command to both CLIs.

### Step 1: Add to `cli-spec.json`

Add a new entry to the `commands` array with all required fields:

```json
{
  "name": "my-command",
  "description": "What this command does.",
  "usage": "mem0 my-command <arg> [OPTIONS]",
  "needsBackend": true,
  "needsConfig": true,
  "resolveIds": true,
  "resolveGraph": false,
  "confirmDangerous": false,
  "outputFormats": ["text", "json"],
  "defaultOutput": "text",
  "arguments": [
    {
      "name": "arg",
      "type": "string",
      "required": true,
      "help": "Argument description."
    }
  ],
  "options": [
    {
      "name": "user_id",
      "flags": ["--user-id", "-u"],
      "type": "string",
      "help": "Scope to user.",
      "panel": "Scope"
    },
    {
      "name": "output",
      "flags": ["--output", "-o"],
      "type": "string",
      "default": "text",
      "help": "Output format.",
      "panel": "Output"
    }
  ],
  "apiEndpoint": "myEndpoint"
}
```

If the command calls a new API endpoint, also add it to `api.endpoints`.

### Step 2: Add Backend Method (if new API endpoint)

**Python** (`python/src/mem0_cli/backend/base.py` and `platform.py`):
1. Add abstract method to `Backend` ABC in `base.py`.
2. Implement in `PlatformBackend` in `platform.py`.

**Node** (`node/src/backend/base.ts` and `platform.ts`):
1. Add method signature to `Backend` interface in `base.ts`.
2. Implement in `PlatformBackend` class in `platform.ts`.

### Step 3: Add Command Handler

**Python** (`python/src/mem0_cli/commands/`):
Create a function `cmd_my_command(backend, ...)` in the appropriate commands file. Follow the patterns:
- Use `timed_status(err_console, "...")` for API calls.
- Use `print_error(err_console, ...)` for errors.
- Use `format_json(console, ...)` for JSON output.
- Raise `typer.Exit(1)` on errors.

**Node** (`node/src/commands/`):
Create an async function `cmdMyCommand(backend, ...)`. Follow the patterns:
- Use `await timedStatus("...", async () => { ... })` for API calls.
- Use `printError(...)` for errors.
- Use `formatJson(...)` for JSON output.
- Call `process.exit(1)` on errors.

### Step 4: Register in App Entrypoint

**Python** (`python/src/mem0_cli/app.py`):
```python
@app.command(name="my-command")
def my_command(
    arg: str = typer.Argument(..., help="..."),
    output: str = typer.Option("text", "--output", "-o", help="...", rich_help_panel="Output"),
    api_key: str | None = typer.Option(None, "--api-key", help="...", rich_help_panel="Connection"),
    base_url: str | None = typer.Option(None, "--base-url", help="...", rich_help_panel="Connection"),
) -> None:
    """Command description."""
    from mem0_cli.commands.my_module import cmd_my_command
    backend, config = _get_backend_and_config(api_key, base_url)
    ids = _resolve_ids(config, ...)
    cmd_my_command(backend, arg, **ids, output=output)
```

**Node** (`node/src/index.ts`):
```typescript
program
  .command("my-command <arg>")
  .description("Command description.")
  .option("-o, --output <format>", "Output format.", "text")
  .option("--api-key <key>", "Override API key.")
  .option("--base-url <url>", "Override API base URL.")
  .action(async (arg, opts) => {
    const { cmdMyCommand } = await import("./commands/my-module.js");
    const { backend, config } = getBackendAndConfig(opts.apiKey, opts.baseUrl);
    const ids = resolveIds(config, opts);
    await cmdMyCommand(backend, arg, { ...ids, output: opts.output });
  });
```

### Step 5: Add Help Examples

Both CLIs include examples in the help text:
- Python: In the docstring of the Typer command function.
- Node: Via `.addHelpText("after", "\nExamples:\n  $ mem0 ...")`.

### Step 6: Add to Help Display and Command Order

**Node** (`node/src/help.ts`):
1. Add `"my-command"` to `COMMAND_ORDER` array (determines display order in `--help`).
2. Add option-to-panel mappings in `OPTION_PANELS["my-command"]`.

**Python**: Options are assigned to panels via `rich_help_panel="..."` on each `typer.Option()`. The `help` command's `_build_help_json()` function needs a new entry.

### Step 7: Add to `help` Command Output

**Python** (`python/src/mem0_cli/app.py`):
1. Add entry in `_build_help_json()` dict.
2. Add line in the `help` command's human-readable output.

**Node** (`node/src/index.ts`):
Add line in the `help` command's human-readable output listing.

### Step 8: Add Tests

- Python: Add tests in `python/tests/`.
- Node: Add tests in `node/src/__tests__/` or similar.

### Step 9: Update This Specification

Add the command to the Complete Command Reference (Section 3) with all arguments, options, behavior notes, and examples.

---

## 10. Adding a New Language Implementation

To add a new language implementation (e.g., Go, Rust, Ruby), you need to replicate the exact behavioral contract defined in `cli-spec.json` and this document. Here is what is required:

### 10.1 Core Modules to Implement

| Module        | Purpose |
|---------------|---------|
| **config**    | Load `~/.mem0/config.json`, apply env var overrides, enforce precedence. Implement `load_config`, `save_config`, `ensure_config_dir`, `redact_key`, `get_nested_value`, `set_nested_value`. |
| **backend/base** | Define the `Backend` interface/trait with all 8 methods: `add`, `search`, `get`, `list_memories`, `update`, `delete`, `delete_entities`, `status`, `entities`. Define error types: `AuthError`, `NotFoundError`, `APIError`. |
| **backend/platform** | Implement `PlatformBackend` with HTTP client. Must implement `_build_filters` logic exactly. Must handle response normalization. Must set `Authorization: Token <key>` header. 30s timeout. |
| **branding**  | Implement print helpers (`print_success`, `print_error`, `print_warning`, `print_info`, `print_scope`), `print_banner`, `timed_status` pattern, `sym` function for Unicode degradation. Colors must match the hex values in `cli-spec.json`. |
| **output**    | Implement `format_memories_text`, `format_memories_table`, `format_single_memory`, `format_add_result`, `format_json`, `format_json_envelope`, `print_result_summary`. Date formatting to YYYY-MM-DD. ID truncation to 8 chars. Memory text truncation to 60 chars in tables. |
| **commands/** | Implement all command handlers matching the exact behavior described in Section 3. |
| **app/main**  | CLI entrypoint with all commands registered. Implement `resolve_ids`, `resolve_graph`, stdin detection, and the `getBackendAndConfig` helper. |
| **help**      | Implement help formatter with grouped option panels (Scope, Search, Pagination, Filters, Output, Connection). Implement `help --json` output. |

### 10.2 Behavioral Checklist

Every new implementation MUST:

- [ ] Read and respect `cli-spec.json` for all command names, descriptions, argument names, option flags, and defaults
- [ ] Implement config precedence: CLI flags > env vars > config file > defaults
- [ ] Implement entity ID resolution (explicit IDs only vs. all defaults)
- [ ] Implement graph tri-state (`--no-graph` > `--graph` > config default)
- [ ] Implement category parsing (JSON first, comma-split fallback)
- [ ] Implement stdin detection and reading for `add`, `search`, `update`
- [ ] Implement `_build_filters` with AND/OR structure
- [ ] Implement response normalization (array vs `{results}` vs `{memories}`)
- [ ] Set config directory permissions to 0700 and file to 0600
- [ ] Implement timed status with spinner on stderr + elapsed time
- [ ] Implement error hierarchy (AuthError 401, NotFoundError 404, APIError 400)
- [ ] Implement `delete --all --project` with wildcard `*` entity IDs and async response handling
- [ ] Implement non-interactive `init` when both `--api-key` and `--user-id` provided
- [ ] Implement `--dry-run` on delete (all modes) and entity delete
- [ ] Implement `--force` on delete --all, delete --entity, and entity delete
- [ ] Send errors to stderr, data to stdout
- [ ] Implement Unicode symbol degradation for non-TTY/NO_COLOR
- [ ] Implement JSON envelope format for status, config show, import
- [ ] Support `--output` on all data-returning commands
- [ ] Implement `help --json` for machine-readable command discovery
- [ ] Implement masked API key input during `init` (echo `*` per character)
- [ ] Implement confirmation prompts for dangerous commands (unless `--force`)
- [ ] Binary must be named `mem0`

### 10.3 Package Metadata

Follow the naming conventions:
- Package description: "The official CLI for mem0 -- the memory layer for AI agents"
- Author: `mem0.ai <founders@mem0.ai>`
- License: Apache-2.0
- Keywords: `mem0`, `memory`, `ai`, `agents`, `cli`

### 10.4 Testing

Conformance tests should verify:
- All commands from `cli-spec.json` are registered
- All options from `cli-spec.json` are accepted
- Config precedence is correct
- Entity ID resolution matches the spec
- Filter building produces correct structures
- Output modes produce expected formats
- Error codes are mapped correctly
- Stdin reading works for supported commands
