# deepseek-plugin

[Mem0](https://mem0.ai) long-term memory as a native [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) (Cordis) plugin.

It gives a Harness agent automatic long-term memory plus two explicit memory tools backed by the Mem0 SDK:

| Capability | Does |
|---|---|
| Auto-recall | Searches Mem0 for the latest human prompt and adds unseen results to the model context |
| Auto-capture | Stores the human/assistant messages from each completed turn |
| `search_memory` | Recall facts from Mem0 relevant to a query |
| `add_memory` | Store a fact in Mem0 for future sessions |

Unlike the local/file-based memory plugins in the ecosystem, Mem0 is a managed backend: server-side extraction, semantic dedup and conflict resolution, and the same memory bank reusable across Harness, Claude Code, Codex, and other agents.

## How it works

A Cordis plugin is a module exporting `apply(ctx, config)`. This one waits for the Harness tool and system-prompt services, then uses the native extension points:

- `system-prompt/assemble` recalls memory before a model request.
- `session/event` captures only completed turns from the durable event stream.
- `ctx.tools.register(...)` exposes explicit search and add tools.

Cordis owns listener and tool cleanup when the plugin unmounts. Every automatic path is fail-open: a memory API failure does not block the agent.

```
[ mem0ai SDK ]  <-- managed memory, owned by Mem0
      |
[ deepseek-plugin: prompt + session listeners, memory tools ]  <-- this package
      |
[ DeepSeek Harness ]  <-- the agent, loaded via cordis.yml
```

## Try it locally

1. Build and pack the plugin:
   ```sh
   cd integrations/deepseek-plugin
   pnpm install --frozen-lockfile
   pnpm build
   mkdir -p /tmp/mem0-deepseek-plugin
   pnpm pack --pack-destination /tmp/mem0-deepseek-plugin
   ```
2. Set your Mem0 key:
   ```sh
   export MEM0_API_KEY=...
   ```
3. Install it into a disposable Harness profile:
   ```sh
   DSH_HOME=/tmp/mem0-dsh-dev pnpm dlx @deepseek-ai/dsh@0.1.1-rc.2 \
     plugin --profile headless add /tmp/mem0-deepseek-plugin/mem0-deepseek-plugin-0.1.1.tgz
   ```
4. Copy `cordis.example.yml`, set its installed package path and your `userId`, then run Harness with the same profile:
   ```sh
   DSH_HOME=/tmp/mem0-dsh-dev pnpm dlx @deepseek-ai/dsh@0.1.1-rc.2 \
     web --patch ./integrations/deepseek-plugin/cordis.example.yml
   ```
5. Open http://127.0.0.1:3080 and ask the agent to remember something, then recall it in a later turn.

For a Mem0 Platform on-prem or dedicated deployment, point `config.host` at that base URL (defaults to `api.mem0.ai`). `host` is a Platform base-URL override — it is not a switch to self-hosted Mem0 OSS, whose server exposes a different API surface.

## Configuration

| Field | Required | Default | Notes |
|---|---|---|---|
| `apiKey` | no | `$MEM0_API_KEY` | Mem0 platform API key |
| `userId` | yes | | Entity that owns the memories |
| `host` | no | `api.mem0.ai` | Platform base URL (on-prem / dedicated) |
| `autoRecall` | no | `true` | Recall relevant memory before model requests |
| `autoCapture` | no | `true` | Store completed human/assistant turns |

## Telemetry

Writes are tagged `source="DEEPSEEK_HARNESS"` so Mem0's backend can attribute usage to this integration. For it to surface by name (rather than bucketing into `OTHERS`), `DEEPSEEK_HARNESS` must be present in the backend's `KNOWN_EVENT_SOURCES` allowlist, a one-line platform change matching the existing `ZAPIER` / `STRANDS` sources.

The plugin also sends anonymous usage events (which tool ran, duration, result counts, coarse failure kind) so Mem0 can tell how the plugin is used and where it breaks. Queries, memory text, and entity ids are never sent. Turn it off with `MEM0_TELEMETRY=false`.

## Status

Developer preview. Tracks the DeepSeek Harness v0.1 plugin API, which is young and moving. Harness capability packages are peer dependencies supplied by the host; this package pins matching release-candidate versions for local typechecking and tests.
