# @mem0/opencode-plugin

Persistent memory for [OpenCode](https://opencode.ai). Your agent remembers decisions, preferences, and learnings across sessions automatically.

## Install

```bash
bunx @mem0/opencode-plugin@latest install
```

Or using OpenCode's built-in CLI:

```bash
opencode plugin @mem0/opencode-plugin
```

**Or let your agent do it** — paste this into OpenCode:

```
Install @mem0/opencode-plugin by following https://raw.githubusercontent.com/mem0ai/mem0/main/mem0-plugin/.opencode-plugin/README.md
```

All commands auto-add the plugin and MCP server to your `~/.config/opencode/opencode.json`. No manual config needed.

Get your API key (free): [app.mem0.ai/dashboard/api-keys](https://app.mem0.ai/dashboard/api-keys)

```bash
echo 'export MEM0_API_KEY="m0-your-key"' >> ~/.zshrc && source ~/.zshrc
```

Restart OpenCode.

## What's included

| Component | Description |
|-----------|-------------|
| **MCP Server** | 9 memory tools — add, search, get, update, delete memories |
| **Lifecycle Hooks** | Auto-search on session start and every prompt, metadata enforcement, error memory lookup, compaction context |
| **16 Slash Commands** | `/mem0:remember`, `/mem0:tour`, `/mem0:stats`, `/mem0:health`, `/mem0:dream`, and more |

## Hooks

Pure TypeScript — no Python, no shell scripts. Uses the [mem0ai](https://www.npmjs.com/package/mem0ai) SDK directly.

| Hook | Event | What it does |
|------|-------|-------------|
| **Chat message** | `chat.message` | Loads prior memories on session start, searches relevant memories before each prompt, auto-captures learnings periodically |
| **Pre-tool** | `tool.execute.before` | Blocks MEMORY.md writes, enforces `user_id`/`app_id` on mem0 tools |
| **Post-tool** | `tool.execute.after` | Tracks stats, scans bash errors for related memories |
| **System transform** | `experimental.chat.system.transform` | Injects memory context (session memories, search results, error lookups) into system prompt |
| **Compaction** | `experimental.session.compacting` | Stores session state memory, then injects prior memories into compaction context so nothing is lost |
| **Shell env** | `shell.env` | Exports `MEM0_USER_ID`, `MEM0_APP_ID`, `MEM0_SESSION_ID`, and `MEM0_BRANCH` to shell |

## MCP Tools

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

## Verify

Start OpenCode and ask: *"Search my memories for recent decisions"*

If the `mem0` tools respond, you're all set.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No tools appearing | Restart OpenCode after installing |
| 401 Unauthorized | `echo $MEM0_API_KEY` must print your `m0-` key |
| Plugin not loading | Run `opencode plugin @mem0/opencode-plugin` again |

## License

Apache-2.0
