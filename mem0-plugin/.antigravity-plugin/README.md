# Mem0 for Google Antigravity

Persistent semantic memory for Antigravity agents — cross-session, user-level, semantic recall via the Mem0 Platform.

## Install

```bash
git clone https://github.com/mem0ai/mem0
agy plugin install ./mem0/mem0-plugin/.antigravity-plugin
agy plugin validate ~/.gemini/config/plugins/mem0   # expect [ok]
```

## Configure

Export your Mem0 API key (get one at [app.mem0.ai/dashboard/api-keys](https://app.mem0.ai/dashboard/api-keys)) in your shell profile:

```bash
echo 'export MEM0_API_KEY="m0-..."' >> ~/.zshrc
source ~/.zshrc
```

The MCP config and lifecycle hooks both read `MEM0_API_KEY` from the environment automatically.

## Verify

Start an Antigravity session and ask the agent to search your memories:

```
Search my memories for recent project decisions
```

The agent should invoke the `mem0:search_memories` tool via MCP.

## Uninstall

```bash
agy plugin uninstall mem0
```

## Windows

`skills/` and `scripts/` are committed as symlinks. On Windows enable symlink support before cloning:

```bash
git config --global core.symlinks true
```

Or use WSL.

## What's Included

- **16 skills** — `/mem0:remember`, `/mem0:forget`, `/mem0:tour`, `/mem0:stats`, `/mem0:health`, and more
- **MCP server** — Remote connection to `https://mcp.mem0.ai/mcp/` (9 tools: add, search, get, update, delete memories + entity management)
- **Lifecycle hooks** — Auto-capture, metadata enforcement, memory-write blocking, bash error scanning
