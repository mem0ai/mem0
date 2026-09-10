# Mem0 agent plugin core

This directory is the single source of shared memory behavior for Mem0 coding-agent plugins. Installable plugins remain ordinary sibling directories under `integrations/`.

## Architecture

```text
integrations/
├── agent-plugin-core/       # Shared source; never installed as a plugin
│   ├── python/              # Claude-derived capture, recall, MCP, scoping, and telemetry
│   ├── typescript/          # Shared lifecycle, formatting, identity, scoping, and telemetry
│   ├── skills/              # The source for six memory skills and the handoff command
│   ├── build/               # Bundle builder, schemas, and validation
│   ├── conformance/         # One offline/live verification entry point
│   └── tests/
├── mem0-agent-plugin/       # One portable Agent Plugins v1 package
├── claude-code-plugin/      # Native Claude package and adapter
├── cursor-plugin/           # Native Cursor package and adapter
├── codex-plugin/            # Native Codex package and adapter
├── kimi-plugin/             # Native Kimi package and adapter
└── antigravity-plugin/      # Native Antigravity package and adapter
```

Each native directory owns only its manifest, native hooks or adapter, tests, and `plugin-build.json`. Its `core/` and `skills/` directories are generated from this module. They are committed because clients install a self-contained plugin directory and the Agent Plugins specification forbids package files from resolving outside the plugin root.

Sidekick belongs only to Claude Code. Its agent definition is in `claude-code-plugin/agents/sidekick.md`; its hooks are in `claude-code-plugin/adapters/claude/hook.py`. Other plugins must not register Sidekick. The shared core handles memory and native subagent tracking for Claude Code and Codex.

TypeScript integrations (`openclaw`, `opencode-plugin`, `pi-agent-plugin`, and `deepseek-plugin`) import `typescript/src/` at build time. Their package builders include the shared implementation in their normal output; they do not carry checked-in copies.

## Shared memory behavior

The six Python packages use the `search_memories` and `handoff_resource` MCP tools, six memory skill templates, and the handoff command. Native hooks collect conversations and flush them to Mem0 in the background. The portable package uses the Agent Plugins v1 layout so compatible hosts can load its MCP server and skills. It has no lifecycle hooks or flush worker; its bundled `remember` skill assumes automatic capture and cannot save a memory on its own.

Search guidance follows Memo: use a focused question when earlier work could help, reuse available context, and search again only for a specific remaining gap. The TypeScript hosts import one shared guidance constant; conformance checks keep it aligned with the generated Python MCP description and reject strict before-answer or repeated-search prompts. Automatic recall schedules and retrieval limits are independent of this wording.

Python search accepts `query`, `top_k`, `category`, `scope`, and optional `run_id`:

| Scope | Memories searched |
| --- | --- |
| `repo` (default) | Shared repository memories and your personal memories in that repository |
| `dir` | Shared memories from the current directory and its children, plus your personal repository memories |
| `mine` | Your personal memories in that repository |

`run_id` filters any scope to memories saved in a known coding-agent session. Omit it for recall across sessions; it does not attribute the search request to the current session. Native Python extraction writes include the session's `run_id`.

New Git repository writes use a hashed remote identity for shared `agent_id`. Search and explicit shared-memory deletion include both that ID and the legacy unhashed ID under the same `app_id`. Legacy memories remain accessible, but their original ambiguity between matching owner/repository names on different Git hosts remains.

Captured prompts and responses preserve their full text after secret redaction. Python extraction splits oversized input across requests without dropping message text. The session-end worker flushes the conversation already collected by hooks without adding the final answer again. Search queries, retrieved context, and tool evidence have separate limits.

TypeScript hosts reuse redaction and lifecycle utilities but retain their own tools, scopes, and capture events. They do not inherit the Python `repo`/`dir`/`mine` contract or its background batching. OpenCode captures selected user prompts; Pi and DeepSeek capture completed conversation turns; OpenClaw selects recent messages and earlier summaries, then filters noise. Removing message-length truncation does not turn these integrations into complete transcript archives.

For installation, follow the host guides: [Claude Code](../../docs/integrations/claude-code.mdx), [Cursor](../../docs/integrations/cursor.mdx), [Codex](../../docs/integrations/codex.mdx), [Kimi](../../docs/integrations/kimi.mdx), and [Antigravity](../../docs/integrations/antigravity.mdx).

## Session handoff

`python/session_handoff.py` is the common launcher. `python/handoff_sources.py` reads native transcripts; `python/handoff_engine.py` validates and stores the shared resource. The transcript conversion is adapted from [mem0ai/memo](https://github.com/mem0ai/memo/blob/aeeb1593284d1d2fca3b4bcf1e32ea10f71df549/docs/session-handoff.md).

All ten plugins save to the same local resource directory, `~/.mem0/handoffs/`. Each resource preserves the source host, session title, project, active user/assistant context, paired tool calls/results, and supported images. Readable compaction context is retained; hidden reasoning and harness configuration are excluded. Unknown model-visible content, missing results, and opaque compaction fail explicitly. Saving never summarizes or truncates the context, runs recorded tools, or launches a destination application.

TypeScript adapters supply native active context through `typescript/src/handoff.ts`; OpenClaw supplies its trusted transcript path. The six Python packages generate one shared `handoff` skill with source-specific instructions. Claude saves before model invocation to avoid capturing the handoff command itself; other Python hosts require an explicit completed transcript or neutral bundle.

To continue in another plugin on the same machine, explicitly ask it to list the current project's handoffs and resume the selected resource. Python plugins expose `handoff_resource` with `action: "list"` or `action: "resume", resource: "/absolute/path.json"`. OpenCode, Pi, and OpenClaw expose `/mem0-handoff list` and `/mem0-handoff resume /absolute/path.json`; DeepSeek exposes the same actions on `mem0_handoff`. Resumed context is historical evidence, not instructions to replay old tools. Project-scoped listing uses the repository root; an explicit resource path also supports continuing in a relocated checkout. This is local storage, not cloud sync.

Handoff requires Python 3.10+ and runs independently of memory hooks and Mem0 credentials. Pi's save action additionally requires Node.js 22.19+ for its native SDK; list and resume remain available on Node.js 20. No destination CLI or model call is required.

The engine source exists only here. Installable packages contain the small launcher and `build/handoff-runtime.json`, which pins a Git commit and SHA-256 digests. On first explicit use, the launcher downloads the two source files from GitHub into `~/.mem0/handoff-runtime/<revision>`. All ten plugins verify and reuse that cache, including offline. A missing or invalid cache requires GitHub access; download or digest failures stop the operation. No transcript is sent to GitHub.

Every TypeScript build uses `build/package_handoff.mjs`; the Python builder uses the same manifest. Builds reject source hashes that differ from the pin, and conformance checks reject stale launchers/manifests. To change the engine, commit its source, pin that immutable commit and its file digests, regenerate Python bundles, and rebuild TypeScript packages. No per-plugin engine edits are needed. Before distributing a new pin, retain its source commit with a `handoff-runtime-<full-commit-sha>` tag. Keep these tags after squash merges and branch deletion so fresh installs can still fetch every distributed runtime. These are retention tags, not package releases.

See the [plugin changelog](../../docs/changelog/sdk.mdx) for invocation details.

## Build and verify

From the repository root:

```bash
python3 -m venv /tmp/mem0-agent-plugins
/tmp/mem0-agent-plugins/bin/pip install \
  -r integrations/agent-plugin-core/requirements-dev.txt

for host in claude-code cursor codex kimi antigravity; do
  /tmp/mem0-agent-plugins/bin/python \
    integrations/agent-plugin-core/build/build.py "$host" \
    --kind native --check
done

/tmp/mem0-agent-plugins/bin/python \
  integrations/agent-plugin-core/build/build.py mem0-agent-plugin \
  --kind portable --check
```

Use `--sync` instead of `--check` after changing `python/` or `skills/`. This only replaces generated `core/` and `skills/` content; it does not change manifests, adapters, tests, or the Claude sidekick.

Run every offline Python and TypeScript check and write one machine-readable report:

```bash
/tmp/mem0-agent-plugins/bin/python \
  integrations/agent-plugin-core/conformance/run.py \
  --install \
  --report /tmp/mem0-plugin-conformance.json
```

For every TypeScript integration, this also builds the publishable package, verifies its required entry files, and rejects compiled artifacts that still import monorepo source. This keeps published plugins self-contained without committing their `dist/` directories.

The offline suite does not contact Mem0 Platform. An explicit disposable key enables the inherited live scoping suite:

```bash
export MEM0_API_KEY="m0-disposable-test-key"
/tmp/mem0-agent-plugins/bin/python \
  integrations/agent-plugin-core/conformance/run.py \
  --group live-platform --live \
  --report /tmp/mem0-plugin-live-conformance.json
```

Do not put a real key in source files, command history shared with others, or pull-request configuration.

## Add a plugin

For another native Python host:

1. Add `integrations/<host>-plugin/` with its native manifest and the smallest adapter that translates host events.
2. Add `plugin-build.json` declaring the plugin-root variable and runtime files.
3. Add one adapter contract test.
4. Register the host in `build/build.py` and `conformance/run.py`.
5. Run `--sync`, `--check`, and the conformance command above.

Keep capture, recall, memory scoping, redaction, skill text, and telemetry in this shared module. Host directories should contain only behavior required by their native SDK.

For a TypeScript host, import the shared lifecycle modules directly and keep only native SDK registration in the integration. Do not advertise capture or compaction behavior unless the host exposes the necessary lifecycle seam. Sidekick is limited to Claude Code.

## Host capture capabilities

| Host | Conversation capture | Tool outcomes | Subagent context and correlation |
| --- | --- | --- | --- |
| Claude Code | Incremental active transcript branch | Native success/failure hooks | Parent context; native agent ID |
| Cursor | Prompt and response hooks; duplicate responses suppressed | Native success/failure hooks | No plugin subagent hooks or agent declaration |
| Codex | Native prompt and final-response fields | Structured failure indicators when present; otherwise unknown | Parent context; native agent ID |
| Kimi | Prompt hooks and completed v2 wire output | Native success/failure hooks | No plugin subagent hooks or agent declaration |
| Antigravity | Incremental completed transcript messages, including later prompts | Native tool errors | No plugin subagent hooks or agent declaration |
| Portable v1 | Explicit memory skills | No native lifecycle hooks | No native subagent declaration |

Python status uses `subagent_runs` and `last_subagent`. Legacy SQLite names and event handling keep existing records and running workers compatible.

An uncorrelated subagent completion is kept as its own record; the plugin never guesses which overlapping run completed. Codex's documented hook fields already match the shared input contract, so no speculative field aliases or unsupported failure event are registered.

Offline conformance exercises the adapters and MCP servers with native-shaped payloads and builds each distributable package. It does not establish that every installed editor or Harness version loads the plugin correctly; those checks require smoke tests in the actual hosts.
