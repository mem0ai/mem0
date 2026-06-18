# @mem0/kilo-plugin

Persistent memory for [Kilo](https://kilo.ai). Your agent remembers decisions, preferences, and learnings across sessions automatically.

Ported from [`@mem0/opencode-plugin`](../mem0-plugin/.opencode-plugin). Kilo's plugin API mirrors OpenCode's, so the hook shapes and memory tools are identical.

## Install

Add `@mem0/kilo-plugin` to your Kilo plugin config (see the [Kilo plugin docs](https://kilo.ai/docs/automate/extending/plugins)). The plugin registers its memory tools itself, there is no MCP server to configure.

Get your API key (free): [app.mem0.ai/dashboard/api-keys](https://app.mem0.ai/dashboard/api-keys)

```bash
echo 'export MEM0_API_KEY="m0-your-key"' >> ~/.zshrc && source ~/.zshrc
```

Restart Kilo.

## What's included

| Component | Description |
|-----------|-------------|
| **10 Native Memory Tools** | `add_memory`, `search_memories`, `get_memories`, `get_memory`, `update_memory`, `delete_memory`, `delete_all_memories`, `delete_entities`, `list_entities`, `get_event_status`, registered as Kilo tools, backed by the `mem0ai` SDK (no MCP server required) |
| **Lifecycle Hooks** | Auto-search on session start and every prompt, error memory lookup, compaction context, secret redaction |

## Hooks

Pure TypeScript, no Python, no shell scripts. Memory operations are native Kilo tools backed by the [mem0ai](https://www.npmjs.com/package/mem0ai) SDK directly.

| Hook | Event | What it does |
|------|-------|-------------|
| **Chat message** | `chat.message` | Loads prior memories on session start, searches relevant memories before each prompt, auto-captures learnings periodically |
| **Pre-tool** | `tool.execute.before` | Blocks MEMORY.md writes, steering them to the `add_memory` tool |
| **Post-tool** | `tool.execute.after` | Scans bash errors and pre-fetches related memories |
| **Messages transform** | `experimental.chat.messages.transform` | Injects memory context (session memories, search results, error lookups) into the prompt |
| **Compaction** | `experimental.session.compacting` | Stores session state memory, then injects prior memories into compaction context so nothing is lost |
| **Shell env** | `shell.env` | Exports `MEM0_USER_ID`, `MEM0_APP_ID`, `MEM0_SESSION_ID`, and `MEM0_BRANCH` to shell |

The TUI skills and slash commands from the OpenCode plugin are intentionally out of scope for this initial release (the linked issue excludes TUI features); they can follow once Kilo's TUI command surface is confirmed.

## Memory Tools

| Tool | Description |
|------|-------------|
| `add_memory` | Save text or conversation history |
| `search_memories` | Semantic search across memories |
| `get_memories` | List memories with filters and pagination |
| `get_memory` | Retrieve a specific memory by ID |
| `update_memory` | Overwrite a memory's text by ID |
| `delete_memory` | Delete a single memory by ID |
| `delete_all_memories` | Bulk delete all memories in scope |
| `delete_entities` | Delete an entity and its memories |
| `list_entities` | List users/agents/apps stored in Mem0 |
| `get_event_status` | Check the status of an async memory operation |

## Memory scope

Every memory tool accepts an optional `scope`. The default scope (used when none is passed) persists in `~/.mem0/settings.json` (`default_scope`) and is read fresh on each memory operation.

| Scope | Reads | Writes |
|-------|-------|--------|
| `project` (default) | this repo (`user_id` + `app_id`) | this repo |
| `session` | this run (adds `run_id`) | this run |
| `global` | all your projects (`app_id="*"`) | user-wide (drops `app_id`) |

`delete_all_memories` always requires an explicit `scope="global"` to delete user-wide, so changing the default can't trigger a cross-project wipe.

## Environment

| Variable | Required | Default |
|----------|----------|---------|
| `MEM0_API_KEY` | yes | none (plugin no-ops without it) |
| `MEM0_USER_ID` | no | OS username |
| `MEM0_APP_ID` | no | git remote `owner-repo`, else repo dir name |
| `MEM0_TELEMETRY` | no | enabled (set `false` to opt out of anonymous usage events) |

## Develop

```bash
bun install
bun run type-check   # tsc --noEmit against @kilocode/plugin types
bun test             # bun:test suites
bun run build        # bundles dist/index.js + emits .d.ts
```

## License

Apache-2.0
