# minimax-mem0

The [Mem0](https://mem0.ai) plugin for the MiniMax Marketplace (MiniMax Code desktop and MiniMax Agent cloud).

It gives a MiniMax agent persistent long-term memory: it remembers the user's preferences, decisions, and project context across sessions and recalls them on demand.

## What's in the package

This is a declarative MiniMax plugin (no build step). It follows the MiniMax plugin spec:

```
minimax-mem0/
  .minimax-plugin/
    plugin.json          # manifest (schemaVersion 1)
  icon.png               # 180x180 square Mem0 icon
  mem0.mcp.json          # remote MCP: https://mcp.mem0.ai/mcp/ (streamable-http)
  skills/
    memory/
      SKILL.md           # when to recall / save / update memory
```

Two capabilities:

- **MCP** (`mem0.mcp.json`) points at Mem0's hosted MCP server (`https://mcp.mem0.ai/mcp/`), which exposes the memory tools (`add_memory`, `search_memories`, `update_memory`, `delete_memory`, and more). No secrets are stored in the package.
- **Skill** (`skills/memory/SKILL.md`) tells the agent when to search, save, update, and delete memory so recall happens automatically.

## Authentication

Mem0's MCP server requires authentication. Per the MiniMax plugin spec, no credentials are placed in this package; the MiniMax client authorizes the user's Mem0 account through the MCP OAuth flow on first use. Users get a Mem0 account from the [Mem0 dashboard](https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=integration-minimax).

## Links

- Mem0: https://mem0.ai
- Mem0 MCP docs: https://docs.mem0.ai/platform/mem0-mcp
