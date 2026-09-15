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

Current package version: `0.3.1`.

Sidekick is available only in the [Claude Code plugin](../claude-code-plugin/README.md#sonnet-sidekick-agent).

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
2. Set your Mem0 key, a stable user identity, and a funded model API key:
   ```sh
   export MEM0_API_KEY=...
   export MEM0_USER_ID=your-user-id
   export DEEPSEEK_API_KEY=...
   ```
3. Install it into a disposable Harness profile:
   ```sh
   DSH_HOME=/tmp/mem0-dsh-dev pnpm dlx @deepseek-ai/dsh@0.1.1-rc.2 \
     plugin --profile web add /tmp/mem0-deepseek-plugin/mem0-deepseek-plugin-0.3.1.tgz
   ```
4. Run Harness with the same profile. The installed bundle activates Mem0 automatically:
   ```sh
   DSH_HOME=/tmp/mem0-dsh-dev pnpm dlx @deepseek-ai/dsh@0.1.1-rc.2 \
     web
   ```
5. Open http://127.0.0.1:3080, select a workspace, and state a synthetic preference without mentioning Mem0. Wait for asynchronous extraction to finish, then start a fresh session and ask for that preference without tools. Inspect the `mem0:recall` context to verify automatic recall.

Build from the full repository: the source imports the sibling shared core. `pnpm pack` runs the build and includes the activation patch. An installed tarball is self-contained. For custom settings, copy `cordis.example.yml` and pass its absolute path with `--patch`. When upgrading from the old manual setup, remove the old patch that **inserts** a `mem0` row; the bundle now inserts it.

On macOS, set `CHOKIDAR_USEPOLLING=1` if Harness reports `EMFILE`. The Mem0 key and model-provider key are separate credentials.

For a Mem0 Platform on-prem or dedicated deployment, point `config.host` at that base URL (defaults to `api.mem0.ai`). `host` overrides the Platform base URL. It does not support the self-hosted Mem0 OSS API.

## Configuration

| Field | Required | Default | Notes |
|---|---|---|---|
| `apiKey` | no | `$MEM0_API_KEY` | Mem0 platform API key |
| `userId` | yes | | Entity that owns the memories |
| `memoryScope` | no | `user` | `user` shares memory across workspaces; `workspace` isolates all automatic and explicit operations by the session workspace |
| `allowUserOverride` | no | `false` | Permit model-selected access to a different user only in a trusted multi-user deployment |
| `host` | no | `api.mem0.ai` | Platform base URL (on-prem / dedicated) |
| `autoRecall` | no | `true` | Recall relevant memory before model requests |
| `autoCapture` | no | `true` | Store completed human/assistant turns |

## Memory scope

Automatic capture and recall use the configured `userId` across sessions. Automatic writes do not attach a repository ID or `runId`.

This cross-workspace sharing is intentional compatibility behavior. Set `memoryScope: workspace` in the profile patch to isolate memory. The plugin then adds an `appId` derived from the canonical absolute session workspace path to every write and the matching `app_id` to every search. Symlink aliases share a scope; different directories (including separate clones or worktrees) do not. Moving a workspace changes its scope. Tools cannot override it. Missing or invalid workspace paths skip automatic memory operations and reject explicit tools, without falling back to user-wide access.

Workspace scope does not migrate existing user-only memories. User scope still searches all memories for that user, including workspace-tagged memories; isolation applies when the plugin is configured with workspace scope. These filters are application-level separation, not separate Mem0 credentials.

Both `search_memory` and `add_memory` accept optional `agentId` and `runId`. On search, these narrow the returned memories; on add, they attach those identities to the stored memory. Pass a known `runId` to search memories explicitly saved with that session ID. This does not include automatically captured user-only memories or identify the session making the request.

Per-call `userId` overrides are rejected unless the operator enables `allowUserOverride: true`. Automatic recall and capture always use the configured user.

## Extraction and recall limits

The plugin sends full redacted completed turns to Mem0; Mem0 extracts the memories asynchronously. A queued write is not proof that every extracted fact is already searchable. Even an initial nonempty memory list can be incomplete. Check the stored memories after processing before diagnosing extraction loss.

Automatic recall is a bounded first pass (up to five results, 4,000 context characters, and a two-second wait). `search_memory` uses a focused query and returns up to ten results by default. Exact preference extraction remains model-dependent; include filenames and numeric constraints in release tests, and distinguish standing preferences from one-off requests.

## Telemetry

Writes are tagged `source="DEEPSEEK_HARNESS"` so Mem0's backend can attribute usage to this integration. For it to surface by name (rather than bucketing into `OTHERS`), `DEEPSEEK_HARNESS` must be present in the backend's `KNOWN_EVENT_SOURCES` allowlist, a one-line platform change matching the existing `ZAPIER` / `STRANDS` sources.

The plugin also sends anonymous usage events (which tool ran, duration, result counts, coarse failure kind) so Mem0 can tell how the plugin is used and where it breaks. Queries, memory text, and entity ids are never sent. Turn it off with `MEM0_TELEMETRY=false`.

## Status

Developer preview. Tracks the DeepSeek Harness v0.1 plugin API, which is young and moving. Harness capability packages are peer dependencies supplied by the host; this package pins matching release-candidate versions for local typechecking and tests.
