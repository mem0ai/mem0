# Mem0 Plugin for Claude

Add persistent memory to your Claude workflows. Store, retrieve, and manage memories across sessions using the Mem0 Platform.

## Installation

```
/plugin install mem0@claude-plugins-official
```

Or browse in `/plugin > Discover`.

## Prerequisites

1. A Mem0 API key from [app.mem0.ai/dashboard/api-keys](https://app.mem0.ai/dashboard/api-keys)
2. Set the environment variable:
   ```bash
   export MEM0_API_KEY="m0-your-api-key"
   ```

## What's included

- **MCP Server** — Connects to the `mem0-mcp-server` via `uvx`, providing tools to add, search, update, and delete memories
- **Mem0 Skill** — Guides Claude on how to integrate the Mem0 SDK (Python & TypeScript) into your applications

## MCP Tools

Once installed, the following tools are available in Claude Code:

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
