# minimax-mem0

The [Mem0](https://mem0.ai) plugin for the MiniMax Marketplace (MiniMax Code desktop and MiniMax Agent cloud).

It gives a MiniMax agent persistent long-term memory: it remembers the user's preferences, decisions, and project context across sessions and recalls them on demand.

## What's in the package

This is a declarative MiniMax plugin (no build step). It follows the MiniMax plugin spec:

Built as a MiniMax **App** (OAuth connect), the same one-click "Connect" experience as peer memory plugins. Mem0's authenticated MCP server is integrated through MiniMax's Connector, so users authorize their Mem0 account once and never handle a key.

```
minimax-mem0/
  .minimax-plugin/
    plugin.json          # manifest: apps + skills
  mem0.app.json          # App capability -> Connector provider (assigned by MiniMax)
  icon.png               # square Mem0 icon
  skills/
    memory/
      SKILL.md           # when to recall / save / update memory
```

Capabilities:

- **App** (`mem0.app.json`) connects the agent to Mem0's OAuth-secured MCP server through MiniMax's Connector (tools: `add_memory`, `search_memories`, `update_memory`, `delete_memory`, and more). The user clicks Connect, authorizes their Mem0 account, done. No secrets in the package.
- **Skill** (`skills/memory/SKILL.md`) tells the agent when to search, save, update, and delete memory so recall happens automatically.

> **Pending:** the App `provider` in `mem0.app.json` is assigned by MiniMax once they complete Connector integration for Mem0's OAuth MCP server. It is a placeholder until then.

## Authentication

Mem0's MCP server requires authentication. Per the MiniMax plugin spec, no credentials are placed in this package; the MiniMax client authorizes the user's Mem0 account through the MCP OAuth flow on first use. Users get a Mem0 account from the [Mem0 dashboard](https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=integration-minimax).

## Links

- Mem0: https://mem0.ai
- Mem0 MCP docs: https://docs.mem0.ai/platform/mem0-mcp
