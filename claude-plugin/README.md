# Mem0 Plugin for Claude

Add persistent memory to your Claude workflows. Store, retrieve, and manage memories across sessions using the Mem0 Platform.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (the MCP server runs via `uvx`)
- A Mem0 Platform account — [sign up at mem0.ai](https://app.mem0.ai)
- A Mem0 API key — go to [app.mem0.ai/dashboard/api-keys](https://app.mem0.ai/dashboard/api-keys), click **Create API Key**, and copy the `m0-...` value
- Add the key to your shell profile (`~/.zshrc` or `~/.bashrc`):
  ```bash
  echo 'export MEM0_API_KEY="m0-your-api-key"' >> ~/.zshrc
  source ~/.zshrc
  ```

## Installation

Add the Mem0 marketplace and install the plugin:

```
/plugin marketplace add mem0ai/mem0
/plugin install mem0@mem0-plugins
```

> **Already have `mem0` configured as an MCP server?** Remove the existing entry from your `.mcp.json` or Claude settings before installing this plugin to avoid duplicate tools.

## What's included

- **MCP Server** — Connects to `mem0-mcp-server` via `uvx`, providing tools to add, search, update, and delete memories
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
