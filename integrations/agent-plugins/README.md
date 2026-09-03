# Mem0 agent plugins

One shared implementation produces self-contained plugins for Claude Code, Cursor, Codex, Kimi, and Antigravity. Claude Code remains the behavioral source of truth; its sidekick prompt is copied byte-for-byte from `shared/sidekick/prompt.md`.

## Layout

- `core/python/`: capture, recall, scoping, MCP, CLI, and telemetry used by Python hosts.
- `core/typescript/`: lifecycle content safety, bounded recall/capture preparation, formatting, identity, scoping, and telemetry reused by TypeScript integrations.
- `shared/`: the only source for portable skill text and the Claude sidekick prompt.
- `hosts/<name>/`: one descriptor, a payload adapter, and native manifest files.
- `dist/<name>/{native,portable}/`: generated, self-contained artifacts with no symlinks.

Host adapters only normalize the host payload and delegate to the shared core. Keep lifecycle policy and memory behavior out of adapters.

## Build and test

The generated plugins support Python 3.10+. Build and specification validation require Python 3.11+ because `skills-ref` requires it.

From the repository root:

```bash
python3.11 -m venv /tmp/mem0-agent-plugins
/tmp/mem0-agent-plugins/bin/pip install -r integrations/agent-plugins/requirements-dev.txt
/tmp/mem0-agent-plugins/bin/python integrations/agent-plugins/scripts/build.py cursor --kind native --output integrations/agent-plugins/dist/cursor/native
/tmp/mem0-agent-plugins/bin/python integrations/agent-plugins/scripts/build.py cursor --kind portable --output integrations/agent-plugins/dist/cursor/portable
/tmp/mem0-agent-plugins/bin/python integrations/agent-plugins/scripts/validate.py integrations/agent-plugins/dist/cursor/portable --kind portable
/tmp/mem0-agent-plugins/bin/python -m pytest integrations/agent-plugins -q
pnpm --dir integrations/agent-plugins/core/typescript test
pnpm --dir integrations/agent-plugins/core/typescript typecheck
```

Replace `cursor` with `claude-code`, `codex`, `kimi`, or `antigravity`.

### Test one plugin

After the one-time Python environment setup above, run one host's adapter tests and build both artifact formats:

```bash
/tmp/mem0-agent-plugins/bin/python -m pytest integrations/agent-plugins/hosts/claude-code/tests -q
/tmp/mem0-agent-plugins/bin/python integrations/agent-plugins/scripts/build.py claude-code --kind native --output /tmp/mem0-claude-code-native
/tmp/mem0-agent-plugins/bin/python integrations/agent-plugins/scripts/build.py claude-code --kind portable --output /tmp/mem0-claude-code-portable
/tmp/mem0-agent-plugins/bin/python integrations/agent-plugins/scripts/validate.py /tmp/mem0-claude-code-portable --kind portable
```

Replace `claude-code` in all four commands with `cursor`, `codex`, `kimi`, or `antigravity`. The live Claude test is intentionally separate because it uses the configured `MEM0_API_KEY` and writes temporary remote memories:

```bash
/tmp/mem0-agent-plugins/bin/python -m pytest integrations/agent-plugins/hosts/claude-code/tests/integration -q
```

Run each independent TypeScript host from the repository root:

```bash
pnpm --dir integrations/agent-plugins/core/typescript test
pnpm --dir integrations/agent-plugins/core/typescript typecheck

pnpm --dir integrations/openclaw test
pnpm --dir integrations/openclaw exec tsc --noEmit
pnpm --dir integrations/openclaw build

pnpm --dir integrations/pi-agent-plugin test
pnpm --dir integrations/pi-agent-plugin typecheck
pnpm --dir integrations/pi-agent-plugin build

pnpm --dir integrations/deepseek-plugin test
pnpm --dir integrations/deepseek-plugin typecheck
pnpm --dir integrations/deepseek-plugin build

cd integrations/opencode-plugin
bun test
bun run type-check
bun run build
```

## How hosts are handled

| Hosts | Runtime | Integration seam |
|---|---|---|
| Claude Code, Cursor, Codex, Kimi, Antigravity | Python | Generated native/portable bundles; thin adapters translate native events into the shared Python lifecycle. |
| Pi | TypeScript | Native session/turn adapter over the shared lifecycle's session, recall, and conversation-capture operations. |
| OpenClaw | TypeScript | Native prompt/agent adapter over the shared lifecycle; retains host-specific ranking, noise filtering, and platform/OSS providers. |
| OpenCode | TypeScript on Bun | Native tool/chat/compaction adapter over the shared lifecycle; retains OpenCode-specific resume and error heuristics. |
| DeepSeek | TypeScript | Native Cordis prompt-assembly, session-event, and tool adapter over the shared lifecycle; automatic recall and completed-turn capture are independently configurable. |

Claude's sidekick remains host-specific. A different host should adopt the same parent-context and lifecycle behavior only through a documented native subagent seam; copying the prompt alone does not create a working sidekick.

## Add a Python host

1. Add `hosts/<name>/host.json`, including the native file mapping and plugin-root token.
2. Add a thin `adapter.py` and only the manifest files required by that host's official plugin format. The shared builder produces both native and portable artifacts from the descriptor.
3. Add an adapter contract test and build both artifacts. Register the native path in the appropriate marketplace without renaming the plugin.

Do not use symlinks or copy shared logic into a host directory. Add sidekick metadata only when that host documents a native subagent format; do not assume Claude's worktree semantics elsewhere.

## Add a TypeScript host

1. Create the host package with its native manifest and SDK dependency.
2. Instantiate `createMemoryLifecycle()` once and translate native session, prompt, capture, and tool events into the operations the host actually supports.
3. Keep redaction, bounds, recall state, timeout, and conversation normalization in `core/typescript/src/lifecycle.ts`; keep host ranking, tool schemas, and unsupported lifecycle behavior in the adapter.
4. Reuse shared formatting, identity, scoping, and telemetry modules instead of copying them.
5. Add lifecycle-interface tests plus the smallest adapter mapping test, then run the host's type check, tests, and build.

Do not advertise automatic capture, pre-compaction flushing, or a sidekick unless the host exposes a real native seam for that behavior.
