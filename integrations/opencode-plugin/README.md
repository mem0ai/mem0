# @mem0/opencode-plugin

Persistent memory for [OpenCode](https://opencode.ai). Your agent remembers decisions, preferences, and learnings across sessions automatically.

Current package version: `0.3.0`. This native TypeScript integration keeps its own tools and scopes while sharing redaction and lifecycle utilities with [agent-plugin-core](../agent-plugin-core/README.md).

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
| **Lifecycle Hooks** | Recall on the first prompt of each session, conversation capture at checkpoints, idle, compaction, and session end, secret redaction |
| **7 Skills** | `/mem0-remember`, `/mem0-tour`, `/mem0-search`, `/mem0-status`, `/mem0-scope`, `/mem0-forget`, `/mem0-context-loader`. Discovered through OpenCode's `skills.paths` |

## Hooks

Written in TypeScript. Memory operations are native OpenCode tools backed by the [mem0ai](https://www.npmjs.com/package/mem0ai) SDK directly.

| Hook | Event | What it does |
|------|-------|-------------|
| **Config** | `config` | Registers the `/mem0-*` slash commands (via `config.command`) and adds the plugin's own `opencode-skills/` dir to OpenCode's `skills.paths` for skill discovery without copying files |
| **Chat message** | `chat.message` | Records each prompt. On the first prompt of a session (20 characters or more) it searches this repository's memories once |
| **Messages transform** | `experimental.chat.messages.transform` | Adds the first-prompt memories to the session's first user message |
| **Text complete** | `experimental.text.complete` | Records the assistant's final response |
| **Session events** | `event` | On `session.idle`, sends the conversation to Mem0 after 5 exchanges, 10 messages, or 40,000 characters, otherwise after 5 idle minutes. On `session.deleted`, sends what is left. Subagent sessions are ignored |
| **Compaction** | `experimental.session.compacting` | Sends the pending conversation before OpenCode compacts it |
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
| `project` (default) | this repo: the shared repository memories plus your own (`user_id` + `app_id`) | this repo |
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

Automatic capture works like the Mem0 Claude Code plugin. The plugin keeps each session's prompts and final assistant responses, redacts secrets, and sends them to Mem0 with `infer=true`. It sends them after 5 exchanges, 10 messages, or 40,000 characters, after 5 idle minutes, before compaction, and when the session is deleted. Mem0 extracts repository facts under a hashed repository `agent_id` and personal facts under your `user_id`, using the same instructions and categories as the Claude Code plugin. The OpenCode session ID is the `run_id`.

Automatic recall runs once per session, on the first prompt of 20 characters or more. It searches this repository's memories (top 5) and adds them to the session's first message. Later prompts do not search automatically. Call `search_memories` or `/mem0-search` when earlier work may help.

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
