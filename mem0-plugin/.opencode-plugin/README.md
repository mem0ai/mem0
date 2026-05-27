# Mem0 for OpenCode

Persistent semantic memory for OpenCode agents — cross-session, user-level, semantic recall via the Mem0 Platform.

## Install

**Option A — Symlink the plugin directory (recommended for repo clones):**

```bash
git clone https://github.com/mem0ai/mem0
ln -s "$(pwd)/mem0/mem0-plugin/.opencode-plugin" ~/.config/opencode/plugins/mem0
```

**Option B — Copy to project plugins:**

```bash
mkdir -p .opencode/plugins/mem0
cp mem0-plugin/.opencode-plugin/opencode-mem0.ts .opencode/plugins/mem0/
cp -r mem0-plugin/scripts .opencode/plugins/mem0/
cp -r mem0-plugin/skills .opencode/plugins/mem0/
```

## Configure

1. Get an API key at [app.mem0.ai/dashboard/api-keys](https://app.mem0.ai/dashboard/api-keys)

2. Export it in your shell profile:

```bash
echo 'export MEM0_API_KEY="m0-..."' >> ~/.zshrc
source ~/.zshrc
```

3. Add the MCP server to your `opencode.json` (project or global):

```json
{
  "mcp": {
    "mem0": {
      "type": "remote",
      "url": "https://mcp.mem0.ai/mcp/",
      "headers": {
        "Authorization": "Token {env:MEM0_API_KEY}"
      },
      "oauth": false
    }
  }
}
```

## Verify

Start an OpenCode session and ask the agent to search your memories:

```
Search my memories for recent project decisions
```

## What's Included

- **TypeScript plugin shim** — Bridges OpenCode events to Mem0 lifecycle hooks (session start, prompt submit, pre/post tool use, compaction)
- **16 skills** — `/mem0:remember`, `/mem0:forget`, `/mem0:tour`, `/mem0:stats`, `/mem0:health`, and more
- **MCP server config** — Remote connection to `https://mcp.mem0.ai/mcp/` (9 tools)
- **Lifecycle hooks** — Auto-capture, metadata enforcement, memory-write blocking, bash error scanning

## Windows

`skills/` and `scripts/` are committed as symlinks. On Windows enable symlink support:

```bash
git config --global core.symlinks true
```

Or use WSL.
