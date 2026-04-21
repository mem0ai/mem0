# Mem0 Plugin for Claude Code, Claude Cowork, Cursor & Codex

Add persistent memory to your AI workflows. Store, retrieve, and manage memories across sessions using the Mem0 Platform. Works with **Claude Code** (CLI), **Claude Cowork** (desktop app), **Cursor**, and **Codex**.

## Step 1: Set your API key

> **You must complete this step before installing the plugin.**

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

Choose one of the options below. All require `MEM0_API_KEY` to be set first (see above).

### Claude Code (CLI) / Claude Cowork (Desktop)

Claude Code and Claude Cowork share the same plugin system.

**CLI:**

```
/plugin marketplace add mem0ai/mem0
/plugin install mem0@mem0-plugins
```

**Cowork desktop app:** Open the Cowork tab, click **Customize** in the sidebar, click **Browse plugins**, and install Mem0.

This installs the full plugin including the MCP server, lifecycle hooks (automatic memory capture), and the Mem0 SDK skill.

### Codex

**Option A — Repo marketplace** (recommended for teams):

Add the plugin marketplace to your repo root (already included in this repository):

```
.agents/plugins/marketplace.json
```

Then in Codex, browse the repo's plugin directory and install Mem0.

**Option B — Personal marketplace**:

Add to `~/.agents/plugins/marketplace.json`:

```json
{
  "name": "mem0-plugins",
  "interface": {
    "displayName": "Mem0 Plugins"
  },
  "plugins": [
    {
      "name": "mem0",
      "source": {
        "source": "local",
        "path": "/path/to/mem0/mem0-plugin"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

**Option C — Manual MCP configuration**:

Add to your Codex MCP config:

```json
{
  "mcpServers": {
    "mem0": {
      "type": "http",
      "url": "https://mcp.mem0.ai/mcp/",
      "headers": {
        "Authorization": "Token ${MEM0_API_KEY}"
      }
    }
  }
}
```

Options A, B, and C above install the MCP server and the Mem0 SDK skill.

**Optional — enable lifecycle hooks**

Codex only discovers hooks at `~/.codex/hooks.json` or `<repo>/.codex/hooks.json` ([docs](https://developers.openai.com/codex/hooks)) — there is no plugin-host mechanism that auto-wires hooks from an installed plugin. To opt in, run the installer once after installing the plugin:

```bash
python3 /path/to/mem0-plugin/scripts/install_codex_hooks.py
```

This merges three entries into `~/.codex/hooks.json` with absolute paths pointing into the plugin directory:

| Event | What it does |
|-------|--------------|
| `SessionStart` | Loads prior memories as bootstrap context |
| `UserPromptSubmit` | Injects relevant memories into the prompt |
| `Stop` | Reminds the agent to persist learnings at turn end |

Re-running the installer is idempotent (replaces the Mem0 entries rather than duplicating) and preserves any other hooks you have. To remove: `python3 scripts/install_codex_hooks.py --uninstall`.

Codex hooks also require the `codex_hooks` feature flag in `~/.codex/config.toml`:

```toml
[features]
codex_hooks = true
```

The installer prints a reminder if the flag isn't set. Restart Codex after editing the config.

### Cursor

> **Already have `mem0` configured as an MCP server?** Remove the existing entry from your Cursor MCP settings before installing to avoid duplicate tools.

**Option A — One-click deeplink** (installs MCP server only):

[Install Mem0 MCP in Cursor](cursor://anysphere.cursor-deeplink/mcp/install?name=mem0&config=eyJtY3BTZXJ2ZXJzIjp7Im1lbTAiOnsidXJsIjoiaHR0cHM6Ly9tY3AubWVtMC5haS9tY3AvIiwiaGVhZGVycyI6eyJBdXRob3JpemF0aW9uIjoiVG9rZW4gJHtlbnY6TUVNMF9BUElfS0VZfSJ9fX19)

**Option B — Manual configuration** (MCP server only):

Add the following to your `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "mem0": {
      "url": "https://mcp.mem0.ai/mcp/",
      "headers": {
        "Authorization": "Token ${env:MEM0_API_KEY}"
      }
    }
  }
}
```

**Option C — Cursor Marketplace** (full plugin with hooks and skills):

Install from the [Cursor Marketplace](https://cursor.com/marketplace) for the complete experience including lifecycle hooks and the Mem0 SDK skill.

## Verify it works

After installing, confirm the MCP server is connected:

1. Start a new session (or restart your current one)
2. Ask: *"List my mem0 entities"* or *"Search my memories for hello"*
3. If the `mem0` tools appear and respond, you're all set

## What's included

| Component | Claude Code / Cowork | Cursor (Marketplace) | Cursor (Deeplink/Manual) | Codex |
|-----------|:--------------------:|:--------------------:|:------------------------:|:-----:|
| MCP Server | Yes | Yes | Yes | Yes |
| Lifecycle Hooks | Yes | Yes | No | Opt-in |
| Mem0 SDK Skill | Yes | Yes | No | Yes |
| Memory Protocol Skill | No | No | No | Yes |

- **MCP Server** — Connects to the Mem0 remote MCP server (`mcp.mem0.ai`), providing tools to add, search, update, and delete memories. No local dependencies required.
- **Lifecycle Hooks** — Automatic memory capture at key points. Claude Code and Cursor wire hooks up natively when the plugin is installed (session start, context compaction, task completion, session end). Codex hooks are opt-in via a one-time installer (`scripts/install_codex_hooks.py`) that writes entries into `~/.codex/hooks.json` for `SessionStart`, `UserPromptSubmit`, and `Stop`.
- **Mem0 SDK Skill** — Guides the AI on how to integrate the Mem0 SDK (Python & TypeScript) into your applications.
- **Memory Protocol Skill** — Codex-specific skill that instructs the agent to retrieve relevant memories at task start, store learnings on completion, and capture session state before context loss. Replaces lifecycle hooks on platforms that don't support them.

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
