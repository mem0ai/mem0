# @mem0/opencode-plugin

Persistent memory for [OpenCode](https://opencode.ai). Your agent remembers decisions, preferences, and learnings across sessions automatically.

Current package version: `0.3.1`. This native TypeScript integration keeps its own tools and scopes while sharing redaction and lifecycle utilities with [agent-plugin-core](../agent-plugin-core/README.md).

Sidekick is available only in the [Claude Code plugin](../claude-code-plugin/README.md#sonnet-sidekick-agent).

## Install

```bash
opencode plugin @mem0/opencode-plugin
```

This adds the plugin to your `~/.config/opencode/opencode.json`. The plugin registers its memory tools and skills. No MCP server configuration is needed.

**Or let your agent do it**: paste this into OpenCode:

```
Install @mem0/opencode-plugin by following https://raw.githubusercontent.com/mem0ai/mem0/main/integrations/opencode-plugin/README.md
```

Get your API key (free): [app.mem0.ai/dashboard/api-keys](https://app.mem0.ai/dashboard/api-keys)

```bash
echo 'export MEM0_API_KEY="m0-your-key"' >> ~/.zshrc && source ~/.zshrc
```

Restart OpenCode.

## What's included

| Component | Description |
|-----------|-------------|
| **10 Native Memory Tools** | `add_memory`, `search_memories`, `get_memories`, `update_memory`, `delete_memory`, and more, backed by the `mem0ai` SDK |
| **Session handoff** | `/mem0-handoff` saves shared context for another plugin |
| **Lifecycle Hooks** | Auto-search on session start and every prompt, error memory lookup, compaction context, secret redaction |
| **7 Skills** | `/mem0-remember`, `/mem0-tour`, `/mem0-search`, `/mem0-status`, `/mem0-scope`, `/mem0-forget`, `/mem0-context-loader`. Discovered through OpenCode's `skills.paths` |

## Session handoff

Run `/mem0-handoff` to save the current session, `/mem0-handoff list` to find this project’s resources, or `/mem0-handoff resume /absolute/path.json` to continue from one.

All plugins share local resources in `~/.mem0/handoffs/`, preserving supported active context, images, and completed tool outcomes. Resume reads that context as historical evidence. Requires **Python 3.10+** as `python3`; no destination CLI or Mem0 credentials are required.

The shared engine is fetched from a pinned GitHub commit on first use, verified, and cached across all plugins. Cached use works offline; no transcript is sent to GitHub. See the [shared handoff logic](../agent-plugin-core/README.md#session-handoff) for source formats and validation.

## Hooks

Memory hooks use TypeScript. Session handoff uses the shared cached Python engine. Memory operations are native OpenCode tools backed by the [mem0ai](https://www.npmjs.com/package/mem0ai) SDK directly.

| Hook | Event | What it does |
|------|-------|-------------|
| **Config** | `config` | Registers the `/mem0-*` slash commands (via `config.command`) and adds the plugin's own `opencode-skills/` dir to OpenCode's `skills.paths` for skill discovery without copying files |
| **Chat message** | `chat.message` | Loads prior memories on session start, searches relevant memories before each prompt, auto-captures learnings periodically |
| **Pre-tool** | `tool.execute.before` | Blocks MEMORY.md writes, steering them to the `add_memory` tool |
| **Post-tool** | `tool.execute.after` | Scans bash errors and pre-fetches related memories |
| **Messages transform** | `experimental.chat.messages.transform` | Injects memory context (session memories, search results, error lookups) into the prompt |
| **Compaction** | `experimental.session.compacting` | Stores session state memory, then injects prior memories into compaction context |
| **Shell env** | `shell.env` | Exports `MEM0_USER_ID`, `MEM0_APP_ID`, `MEM0_SESSION_ID`, and `MEM0_BRANCH` to shell |

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
| `get_event_status` | Check the processing status of an asynchronous memory event |

## Memory scope

`add_memory`, `search_memories`, `get_memories`, and `delete_all_memories` accept an optional `scope`. You can set the **default**
scope (used when none is passed) with the `/mem0-scope` skill:

| Scope | Reads | Writes |
|-------|-------|--------|
| `project` (default) | this repo (`user_id` + `app_id`) | this repo |
| `session` | this run (adds `run_id`) | this run |
| `global` | all your projects (filtered by your user ID) | user-wide (drops `app_id`) |

```
/mem0-scope            # show the current default scope
/mem0-scope global     # save & search across all your projects by default
/mem0-scope project    # back to repo-only (default)
```

The default persists in `~/.mem0/settings.json` (`default_scope`) and is read
fresh on each memory operation, so changes apply without a restart.
`delete_all_memories` always requires an explicit `scope="global"` to delete
user-wide, so changing the default can't trigger a cross-project wipe.

## Capture and session context

Automatic capture saves every third qualifying user prompt. Other exchanges and assistant conclusions can be saved through `add_memory` or the remember skill; this is not a complete transcript recorder. Captured and explicitly saved text is redacted without the former 6,000-character cutoff.

Automatic capture uses the user and repository IDs, with the session ID in metadata. Explicit `session`-scope writes and searches use the top-level `run_id` filter. A session-scoped search therefore does not automatically include project memories that only carry `metadata.session_id`.

These `project`/`session`/`global` scopes are specific to this integration, not the Python plugins' `repo`/`dir`/`mine` scopes. Global tool access requires the user to enable it through `/mem0-scope global` or plugin settings first.

## Verify

Start OpenCode and ask: *"Search my memories for recent decisions"*

If the `mem0` tools respond, you're all set.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No tools appearing | Restart OpenCode after installing |
| 401 Unauthorized | Check that `MEM0_API_KEY` is set to a valid key without printing it |
| Plugin not loading | Run `opencode plugin @mem0/opencode-plugin` again |

## License

Apache-2.0
