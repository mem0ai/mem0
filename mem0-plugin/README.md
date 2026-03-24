# Mem0 Plugin for Claude & Cursor

Add persistent memory to your AI coding workflows. Store, retrieve, and manage memories across sessions using the Mem0 Platform. Works with both **Claude Code** and **Cursor**.

## Step 1: Set your API key

> **You must complete this step before installing the plugin for either Claude Code or Cursor.**

1. Sign up at [app.mem0.ai](https://app.mem0.ai) if you haven't already
2. Go to [app.mem0.ai/dashboard/api-keys](https://app.mem0.ai/dashboard/api-keys)
3. Click **Create API Key** and copy the key (starts with `m0-`)
4. Add it to your shell profile:

   ```bash
   # For zsh (default on macOS)
   echo 'export MEM0_API_KEY="m0-your-api-key"' >> ~/.zshrc
   source ~/.zshrc

   # For bash
   echo 'export MEM0_API_KEY="m0-your-api-key"' >> ~/.bashrc
   source ~/.bashrc
   ```

5. Confirm it's set:

   ```bash
   echo $MEM0_API_KEY
   # Should print: m0-your-api-key
   ```

## Step 2: Install the plugin

Choose one of the options below. Both require `MEM0_API_KEY` to be set first (see above).

### Claude Code

```
/plugin marketplace add mem0ai/mem0
/plugin install mem0@mem0-plugins
```

### Cursor

Install from the Cursor Marketplace by searching for **mem0**, or use the one-click deeplink below.

[Install Mem0 MCP in Cursor](cursor://anysphere.cursor-deeplink/mcp/install?name=mem0&config=eyJtY3BTZXJ2ZXJzIjp7Im1lbTAiOnsidHlwZSI6Imh0dHAiLCJ1cmwiOiJodHRwczovL21jcC5tZW0wLmFpL21jcC8iLCJoZWFkZXJzIjp7IkF1dGhvcml6YXRpb24iOiJUb2tlbiAke01FTTBfQVBJX0tFWX0ifX19fQ==)

> **Already have `mem0` configured as an MCP server?** Remove the existing entry from your `.mcp.json` or settings before installing this plugin to avoid duplicate tools.

## Verify it works

After installing, confirm the MCP server is connected:

1. Start a new session (or restart your current one)
2. Ask: *"List my mem0 entities"* or *"Search my memories for hello"*
3. If the `mem0` tools appear and respond, you're all set

## What's included

- **MCP Server** — Connects to the Mem0 remote MCP server (`mcp.mem0.ai`), providing tools to add, search, update, and delete memories. No local dependencies required.
- **Mem0 Skill** — Guides Claude on how to integrate the Mem0 SDK (Python & TypeScript) into your applications

## MCP Tools

Once installed, the following tools are available:

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
