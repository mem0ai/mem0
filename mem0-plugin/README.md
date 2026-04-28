# Mem0 Plugin for Claude Code, Claude Cowork, Cursor & Codex

Add persistent memory to your AI workflows. Store, retrieve, and manage memories across sessions using the Mem0 Platform. Works with **Claude Code** (CLI), **Claude Cowork** (desktop app), **Cursor**, and **Codex**.

## Step 1: Set your API key

> **You must complete this step before installing the plugin.**

1. Sign up at [app.mem0.ai](https://app.mem0.ai?utm_source=oss&utm_medium=mem0-plugin-readme) if you haven't already
2. Go to [app.mem0.ai/dashboard/api-keys](https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=mem0-plugin-readme)
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

**Option A — Direct MCP** (fastest, MCP only):

Codex reads MCP servers from `~/.codex/config.toml` as TOML. Add:

```toml
[mcp_servers.mem0]
url = "https://mcp.mem0.ai/mcp"
bearer_token_env_var = "MEM0_API_KEY"
```

Export `MEM0_API_KEY` in your shell and restart Codex. `codex mcp add` only supports stdio servers, so HTTP servers like Mem0's must be added via `config.toml` directly (or via the **Plugins → Connect to a custom MCP → Streamable HTTP** UI in the Codex app).

**Option B — Sideload the plugin** (full experience: MCP + skills + opt-in hooks):

Clone the repo and register the bundled marketplace with one CLI call:

```bash
git clone https://github.com/mem0ai/mem0.git ~/codex-plugins/mem0-source
codex plugin marketplace add ~/codex-plugins/mem0-source
```

This points Codex at the repo's `.agents/plugins/marketplace.json`, which references `mem0-plugin/` as the local source. Restart Codex, run `/plugins`, and install **Mem0** from the **Mem0 Plugins** marketplace.

> **Don't combine with Option A.** The plugin manifest auto-registers `mem0` as an MCP server via `mem0-plugin/.codex-mcp.json` — adding a manual `[mcp_servers.mem0]` block would duplicate the registration.

**Optional — enable lifecycle hooks.** Codex doesn't auto-wire hooks from plugin manifests; it only reads `~/.codex/hooks.json` (or `<repo>/.codex/hooks.json`) ([docs](https://developers.openai.com/codex/hooks)). Run the bundled installer once to merge Mem0's entries:

```bash
python3 ~/codex-plugins/mem0-source/mem0-plugin/scripts/install_codex_hooks.py
```

This merges three entries into `~/.codex/hooks.json` with absolute paths pointing into your clone:

| Event | What it does |
|-------|--------------|
| `SessionStart` | Loads prior memories as bootstrap context |
| `UserPromptSubmit` | Injects relevant memories into the prompt |
| `Stop` | Reminds the agent to persist learnings at turn end |

Re-running the installer is idempotent (replaces the Mem0 entries rather than duplicating) and preserves any other hooks you have. To remove: `python3 .../install_codex_hooks.py --uninstall`. If you move or delete the clone directory, re-run the installer from the new location — the hooks file stores absolute paths.

Codex hooks also require the `codex_hooks` feature flag in `~/.codex/config.toml`:

```toml
[features]
codex_hooks = true
```

The installer prints a reminder if the flag isn't set. Restart Codex after editing the config.

**Managing the plugin:**

```bash
codex plugin marketplace upgrade               # pull latest plugin versions
codex plugin marketplace remove mem0-plugins   # unregister the marketplace
```

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

| Component | Claude Code / Cowork | Cursor (Marketplace) | Cursor (Deeplink/Manual) | Codex (Sideload) | Codex (Direct MCP) |
|-----------|:--------------------:|:--------------------:|:------------------------:|:----------------:|:------------------:|
| MCP Server | Yes | Yes | Yes | Yes | Yes |
| Lifecycle Hooks | Yes | Yes | No | Opt-in | No |
| Mem0 SDK Skill | Yes | Yes | No | Yes | No |
| Memory Protocol Skill | No | No | No | Yes | No |

- **MCP Server** — Connects to the Mem0 remote MCP server (`mcp.mem0.ai`), providing tools to add, search, update, and delete memories. No local dependencies required.
- **Lifecycle Hooks** — Automatic memory capture at key points. Claude Code and Cursor wire hooks up natively when the plugin is installed (session start, context compaction, task completion, session end). Codex hooks are opt-in via a one-time installer (`scripts/install_codex_hooks.py`) that writes entries into `~/.codex/hooks.json` for `SessionStart`, `UserPromptSubmit`, and `Stop`.
- **Mem0 SDK Skill** — Guides the AI on how to integrate the Mem0 SDK (Python & TypeScript) into your applications.
- **Memory Protocol Skill** — Codex-specific skill that instructs the agent to retrieve relevant memories at task start, store learnings on completion, and capture session state before context loss. Complements the lifecycle hooks on Codex.

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
