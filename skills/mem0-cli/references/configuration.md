# Mem0 CLI Configuration

Everything about configuring the mem0 CLI: config file format, environment variables, the init wizard, and precedence rules.

---

## Config File Location

| Path | Permissions | Description |
|------|-------------|-------------|
| `~/.mem0/` | `0700` (owner rwx) | Config directory. Created automatically by `mem0 init`. |
| `~/.mem0/config.json` | `0600` (owner rw) | Config file. Contains API key, defaults, and platform settings. |

The restricted permissions ensure API keys are not world-readable.

Saving an API key also updates an existing `env.MEM0_API_KEY` entry in `~/.claude/settings.json` and existing `export MEM0_API_KEY=...` lines in `~/.zshrc`, `~/.bashrc`, and `~/.bash_profile`. It never creates new entries.

---

## Config File Schema

```json
{
  "version": 1,
  "defaults": {
    "user_id": "",
    "agent_id": "",
    "app_id": "",
    "run_id": ""
  },
  "platform": {
    "api_key": "",
    "base_url": "https://api.mem0.ai",
    "user_email": "",
    "agent_mode": false,
    "created_via": "",
    "agent_caller": "",
    "claimed_at": "",
    "default_user_id": ""
  },
  "telemetry": {
    "anonymous_id": ""
  },
  "agent_rush": {
    "acknowledged_at": ""
  }
}
```

### Field Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `version` | integer | `1` | Config schema version. |
| `defaults.user_id` | string | `""` | Default user ID for scoping commands. |
| `defaults.agent_id` | string | `""` | Default agent ID for scoping commands. |
| `defaults.app_id` | string | `""` | Default app ID for scoping commands. |
| `defaults.run_id` | string | `""` | Default run ID for scoping commands. |
| `platform.api_key` | string | `""` | API key for the Mem0 Platform. |
| `platform.base_url` | string | `"https://api.mem0.ai"` | Base URL for API requests. |
| `platform.user_email` | string | `""` | Email used for login or claim. Also cached from the ping response during `init`. |
| `platform.agent_mode` | boolean | `false` | `true` while the key is an unclaimed Agent Mode key. |
| `platform.created_via` | string | `""` | How the key was obtained: `agent_mode`, `email`, `api_key`, or `existing_key`. |
| `platform.agent_caller` | string | `""` | Agent name set by `--agent-caller` or `mem0 identify`. |
| `platform.claimed_at` | string | `""` | ISO timestamp once an Agent Mode account is claimed. |
| `platform.default_user_id` | string | `""` | `user_<slug>` returned by the Agent Mode bootstrap. Printed by `mem0 whoami`. |
| `telemetry.anonymous_id` | string | `""` | Persistent anonymous ID used for telemetry. |
| `agent_rush.acknowledged_at` | string | `""` | ISO timestamp when the `agent-rush` public-memory warning was acknowledged. |

---

## `mem0 init` Wizard

The `init` command provides three authentication flows: API key, email login, and Agent Mode (see [Agent Mode Init](#agent-mode-init)).

### API Key Flow (default)

```bash
# Fully interactive:
mem0 init

# Fully non-interactive:
mem0 init --api-key m0-xxx --user-id alice
```

**Interactive mode steps:**

1. Displays the mem0 banner.
2. Checks for existing config. If found with an API key, asks for confirmation to overwrite.
3. Asks how to authenticate (`1` email login, recommended; `2` enter an API key) unless `--api-key` was passed.
4. For option 2, prompts for the API key (input masked with `*` characters; supports backspace and Ctrl+U to clear).
5. Prompts for default user ID (default value: `$USER`, then `$USERNAME`, then `mem0-cli`) unless `--user-id` was passed.
6. Validates the connection by calling the status endpoint. A failed check prints an error but the config is still saved.
7. Saves config to `~/.mem0/config.json` with `0600` permissions.
8. Prints success message.

**Non-interactive mode:** When both `--api-key` and `--user-id` are provided, skips all prompts and saves directly. In a non-TTY, `--api-key` alone is enough: the user ID falls back to `$USER`, then `$USERNAME`, then `mem0-cli`. A non-TTY without `--api-key` (and without `--email` or an Agent Mode signal) prints an error:

```
Non-interactive terminal detected and --api-key is required.
```

### Email Login Flow

```bash
# Interactive (prompts for code):
mem0 init --email alice@company.com

# Fully non-interactive:
mem0 init --email alice@company.com --code 482901
```

**Steps:**

1. Sends a 6-digit verification code to the email via `POST /api/v1/auth/email_code/`.
2. If `--code` is provided, verifies immediately. Otherwise prompts for the code.
3. On success: receives the API key from the server and saves it with `platform.user_email` and `platform.created_via: "email"`. The default user ID is `--user-id`, else `$USER`, else `mem0-cli`.

Without `--code` in a non-TTY, `init` sends the code and exits with an error telling you to rerun with `--code`. `--code` requires `--email`, and `--email` cannot be combined with `--api-key`.

**Claiming an Agent Mode account:** If the existing config is an unclaimed Agent Mode key (`platform.agent_mode: true`), `mem0 init --email <email> [--code <code>]` claims that key for the email instead of minting a new one. The API key stays the same.

### Agent Mode Init

```bash
mem0 init --agent --agent-caller <name> --json
```

With `init --agent`, `init --json`, or an agent environment variable (such as `CLAUDECODE`, `CURSOR_AGENT`, `CODEX_CLI`, `CLINE`, `AIDER_SESSION`, `GOOSE_AGENT`, `WINDSURF_AGENT`) and no `--api-key` or `--email`, `init` first reuses a valid `MEM0_API_KEY` or a valid key already in the config. Only when there is no valid key does it mint a new Agent Mode key via `POST /api/v1/auth/agent_mode/`, which is limited to 5 signups per day per network. See [command-reference.md](command-reference.md) for the `init` flags and `identify`.

### Force Overwrite

If `~/.mem0/config.json` already exists with an API key, `mem0 init` warns and asks for confirmation (in a non-TTY it exits 1 with "Existing config would be overwritten." instead). Use `--force` to skip:

```bash
mem0 init --api-key m0-new-key --user-id alice --force
```

---

## `mem0 config` Subcommands

### `mem0 config show`

Displays `defaults.*`, `platform.api_key` (redacted), and `platform.base_url` as a formatted table (text mode) or JSON envelope (json mode). Other `platform.*` fields are not shown.

```bash
mem0 config show
mem0 config show -o json
```

### `mem0 config get <key>`

Reads a single configuration value. The key uses dotted notation or a short alias (`api_key`, `base_url`, `user_email`, `user_id`, `agent_id`, `app_id`, `run_id`).

```bash
mem0 config get platform.api_key     # prints: m0-x...xxxx (redacted)
mem0 config get defaults.user_id     # prints: alice
```

**Valid keys:**
- `platform.api_key`
- `platform.base_url`
- `platform.user_email`
- `defaults.user_id`
- `defaults.agent_id`
- `defaults.app_id`
- `defaults.run_id`

Python also resolves any other field path in the config (for example `platform.created_via`); Node accepts only the keys above and their short aliases. Unknown keys print "Unknown config key: <key>" and still exit 0, so check the output rather than the exit code. In `--json`/`--agent` mode `config get` and `config set` return `{"key": ..., "value": ...}` in the envelope.

### `mem0 config set <key> <value>`

Sets a configuration value and saves the config file.

```bash
mem0 config set defaults.user_id alice
mem0 config set platform.base_url https://api.mem0.ai
```

**Type coercion:**
- Boolean fields accept `true`, `1`, `yes` (case-insensitive) as true. Anything else is false.
- Integer fields are parsed as integers (Node `parseInt`, Python `int`; Python rejects a non-numeric value as an unknown key).
- String fields are stored as-is.

---

## Environment Variables

Environment variables override config file values but are overridden by CLI flags.

| Variable | Config Path | Type | Default |
|----------|-------------|------|---------|
| `MEM0_API_KEY` | `platform.api_key` | string | `""` |
| `MEM0_BASE_URL` | `platform.base_url` | string | `"https://api.mem0.ai"` |
| `MEM0_USER_ID` | `defaults.user_id` | string | `""` |
| `MEM0_AGENT_ID` | `defaults.agent_id` | string | `""` |
| `MEM0_APP_ID` | `defaults.app_id` | string | `""` |
| `MEM0_RUN_ID` | `defaults.run_id` | string | `""` |
| `MEM0_TELEMETRY` | n/a | string | enabled. Set to `false` to disable anonymous telemetry. |

---

## Precedence

Configuration values are resolved in this order (highest priority first):

```
1. CLI flags        --api-key, --user-id, --base-url, etc.
2. Environment vars MEM0_API_KEY, MEM0_USER_ID, etc.
3. Config file      ~/.mem0/config.json
4. Defaults         Hardcoded defaults (empty strings, false, https://api.mem0.ai)
```

**Example:** If your config file has `user_id: "bob"`, the env var `MEM0_USER_ID=charlie` is set, and you pass `--user-id alice` on the command line, the effective user_id is `alice`.

---

## API Key Redaction Rules

Whenever an API key is displayed (in `config show`, `config get`, status output, etc.), it is redacted:

| Condition | Output |
|-----------|--------|
| Empty string | `(not set)` |
| Length <= 8 | First 2 characters + `***` |
| Length > 8 | First 4 characters + `...` + last 4 characters |

**Examples:**
- `""` -> `(not set)`
- `"m0-abc"` -> `m0***`
- `"m0-abcdefghijklmnop"` -> `m0-a...mnop`

The redaction function is named `redact_key` (Python) / `redactKey` (Node).

---

## Dotted Key Map

The `config get` and `config set` commands use dotted key paths. Here is the full mapping:

| Dotted Key | Section | Field |
|------------|---------|-------|
| `platform.api_key` | platform | api_key |
| `platform.base_url` | platform | base_url |
| `platform.user_email` | platform | user_email |
| `defaults.user_id` | defaults | user_id |
| `defaults.agent_id` | defaults | agent_id |
| `defaults.app_id` | defaults | app_id |
| `defaults.run_id` | defaults | run_id |

Short aliases (`api_key`, `base_url`, `user_email`, `user_id`, `agent_id`, `app_id`, `run_id`) map to the same fields. Python additionally resolves any other dotted field path.
