# deepseek-plugin

[Mem0](https://mem0.ai) long-term memory as a native [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) (Cordis) plugin.

It gives a Harness agent automatic long-term memory plus two explicit memory tools backed by the Mem0 SDK:

| Capability | Does |
|---|---|
| Auto-recall | Searches Mem0 for the latest human prompt and adds unseen results to the model context |
| Auto-capture | Stores the human/assistant messages from each completed turn |
| `search_memory` | Recall facts from Mem0 relevant to a query |
| `add_memory` | Store a fact in Mem0 for future sessions |

Unlike the local/file-based memory plugins in the ecosystem, Mem0 is a managed backend: server-side extraction, semantic dedup and conflict resolution, and memories that other agents can retrieve when their user and entity filters match.

Current package version: `0.3.0`.

## How it works

A Cordis plugin is a module exporting `apply(ctx, config)`. This one waits for the Harness tool and system-prompt services, then uses the native extension points:

- `system-prompt/assemble` recalls memory before a model request.
- `session/event` captures only completed turns from the durable event stream.
- `ctx.tools.register(...)` exposes explicit search and add tools.

Completed human and assistant text is preserved after secret redaction, without the former 6,000-character per-message cutoff. Recall queries and displayed tool results retain separate size limits. These behaviors use [agent-plugin-core](../agent-plugin-core/README.md); this integration keeps its native tools and user-based scoping.

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
     plugin --profile headless add /tmp/mem0-deepseek-plugin/mem0-deepseek-plugin-0.3.0.tgz
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
| `allowUserOverride` | no | `false` | Permit model-selected access to a different user only in a trusted multi-user deployment |
| `host` | no | `api.mem0.ai` | Platform base URL (on-prem / dedicated) |
| `autoRecall` | no | `true` | Recall relevant memory before model requests |
| `autoCapture` | no | `true` | Store completed human/assistant turns |

## Memory scope

Automatic capture and recall use the configured `userId` across sessions. Automatic writes do not attach a repository ID or `runId`.

Both `search_memory` and `add_memory` accept optional `agentId` and `runId`. On search, these narrow the returned memories; on add, they attach those identities to the stored memory. Pass a known `runId` to search memories explicitly saved with that session ID. This does not include automatically captured user-only memories or identify the session making the request.

Per-call `userId` overrides are rejected unless the operator enables `allowUserOverride: true`. Automatic recall and capture always use the configured user.

## Telemetry

Writes are tagged `source="DEEPSEEK_HARNESS"` so Mem0's backend can attribute usage to this integration. For it to surface by name (rather than bucketing into `OTHERS`), `DEEPSEEK_HARNESS` must be present in the backend's `KNOWN_EVENT_SOURCES` allowlist, a one-line platform change matching the existing `ZAPIER` / `STRANDS` sources.

The plugin also sends anonymous usage events (which tool ran, duration, result counts, coarse failure kind) so Mem0 can tell how the plugin is used and where it breaks. Queries, memory text, and entity ids are never sent. Turn it off with `MEM0_TELEMETRY=false`.

## Status

Developer preview. Tracks the DeepSeek Harness v0.1 plugin API, which is young and moving. Harness capability packages are peer dependencies supplied by the host; this package pins matching release-candidate versions for local typechecking and tests.
