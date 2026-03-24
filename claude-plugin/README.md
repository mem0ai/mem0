# Mem0 Plugin for Claude

Add persistent memory to your Claude workflows. Store, retrieve, and manage memories across sessions using the Mem0 Platform.

## Prerequisites

- A Mem0 Platform account — [sign up at mem0.ai](https://app.mem0.ai)

### Set up your API key

1. Go to [app.mem0.ai/dashboard/api-keys](https://app.mem0.ai/dashboard/api-keys)
2. Click **Create API Key** and copy the key (starts with `m0-`)
3. Add it to your shell profile:

   ```bash
   # For zsh (default on macOS)
   echo 'export MEM0_API_KEY="m0-your-api-key"' >> ~/.zshrc
   source ~/.zshrc

   # For bash
   echo 'export MEM0_API_KEY="m0-your-api-key"' >> ~/.bashrc
   source ~/.bashrc
   ```

4. Confirm it's set:

   ```bash
   echo $MEM0_API_KEY
   # Should print: m0-your-api-key
   ```

## Installation

Add the Mem0 marketplace and install the plugin:

```
/plugin marketplace add mem0ai/mem0
/plugin install mem0@mem0-plugins
```

> **Already have `mem0` configured as an MCP server?** Remove the existing entry from your `.mcp.json` or Claude settings before installing this plugin to avoid duplicate tools.

## Verify it works

After installing, confirm the MCP server is connected:

1. Start a new Claude Code session (or restart your current one)
2. Ask Claude: *"List my mem0 entities"* or *"Search my memories for hello"*
3. If the `mem0` tools appear and respond, you're all set

## What's included

- **MCP Server** — Connects to the Mem0 remote MCP server (`mcp.mem0.ai`), providing tools to add, search, update, and delete memories. No local dependencies required.
- **Mem0 Skill** — Guides Claude on how to integrate the Mem0 SDK (Python & TypeScript) into your applications

## MCP Tools

Once installed, the following tools are available in Claude:

| Tool | Description |
|------|-------------|
| `add_memory` | Save text or conversation history for a user/agent |
| `search_memories` | Semantic search across memories with filters |
| `get_memories` | List memories with filters and pagination |
| `get_memory` | Retrieve a specific memory by ID |
| `update_memory` | Overwrite a memory's text by ID |
| `delete_memory` | Delete a single memory by ID |
| `delete_all_memories` | Bulk delete all memories in scope |
| `delete_entities` | Delete a user/agent/app/run entity and its memories |
| `list_entities` | List users/agents/apps/runs stored in Mem0 |

## License

Apache-2.0
