# deepseek-plugin

[Mem0](https://mem0.ai) long-term memory as a native [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) (Cordis) plugin.

It gives a Harness agent two memory tools backed by the Mem0 SDK, so recall and writes persist across sessions:

| Tool | Does |
|---|---|
| `search_memory` | Recall facts from Mem0 relevant to a query |
| `add_memory` | Store a fact in Mem0 for future sessions |

Unlike the local/file-based memory plugins in the ecosystem, Mem0 is a managed backend: server-side extraction, semantic dedup and conflict resolution, and the same memory bank reusable across Harness, Claude Code, Codex, and other agents.

## How it works

A Cordis plugin is a module exporting `apply(ctx, config)`. This one declares `inject = ['tools']` so it waits for the harness tool registry, then registers the two tools via `ctx.tools.register(defineTool(...))`. When the plugin unmounts, the tools are removed automatically (Cordis revertible effects).

```
[ mem0ai SDK ]  <-- managed memory, owned by Mem0
      |
[ deepseek-plugin: apply(ctx) -> ctx.tools.register(...) ]  <-- this package
      |
[ DeepSeek Harness ]  <-- the agent, loaded via cordis.yml
```

## Try it locally

1. Build the plugin:
   ```sh
   cd integrations/deepseek-plugin
   pnpm install
   pnpm build
   ```
2. Set your Mem0 key:
   ```sh
   export MEM0_API_KEY=...
   ```
3. Point Harness at it. Copy `cordis.example.yml`, set the absolute path to `dist/index.js` and your `userId`, then:
   ```sh
   pnpm dsh web --patch ./integrations/deepseek-plugin/cordis.example.yml
   ```
4. Open http://127.0.0.1:3080 and ask the agent to remember something, then recall it in a later turn.

For a Mem0 Platform on-prem or dedicated deployment, point `config.host` at that base URL (defaults to `api.mem0.ai`). `host` is a Platform base-URL override — it is not a switch to self-hosted Mem0 OSS, whose server exposes a different API surface.

## Configuration

| Field | Required | Default | Notes |
|---|---|---|---|
| `apiKey` | no | `$MEM0_API_KEY` | Mem0 platform API key |
| `userId` | yes | | Entity that owns the memories |
| `host` | no | `api.mem0.ai` | Platform base URL (on-prem / dedicated) |

## Telemetry

Writes are tagged `source="DEEPSEEK_HARNESS"` so Mem0's backend can attribute usage to this integration. For it to surface by name (rather than bucketing into `OTHERS`), `DEEPSEEK_HARNESS` must be present in the backend's `KNOWN_EVENT_SOURCES` allowlist, a one-line platform change matching the existing `ZAPIER` / `STRANDS` sources.

The plugin also sends anonymous usage events (which tool ran, duration, result counts, coarse failure kind) so Mem0 can tell how the plugin is used and where it breaks. Queries, memory text, and entity ids are never sent. Turn it off with `MEM0_TELEMETRY=false`.

## Status

Developer preview. Tracks the DeepSeek Harness v0.1 plugin API (`@deepseek-ai/cordis`, `@deepseek-ai/dsh-tools`), which is young and moving; pin versions once it stabilizes. Auto-capture (store turns without an explicit tool call) and auto-recall (inject memory into the prompt at assembly) are planned once the harness session/assembly event API is confirmed.
