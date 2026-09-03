# Mem0 agent plugin core

This directory is the single source of shared memory behavior for Mem0 coding-agent plugins. Installable plugins remain ordinary sibling directories under `integrations/`.

## Architecture

```text
integrations/
├── agent-plugin-core/       # Shared source; never installed as a plugin
│   ├── python/              # Claude-derived capture, recall, MCP, scoping, and telemetry
│   ├── typescript/          # Shared lifecycle, formatting, identity, scoping, and telemetry
│   ├── skills/              # The only source for the six generated memory skills
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

Claude Code remains the behavioral source of truth. Its sidekick stays at `claude-code-plugin/agents/sidekick.md` and is not generated or copied to hosts without a compatible native subagent interface.

TypeScript integrations (`openclaw`, `opencode-plugin`, `pi-agent-plugin`, and `deepseek-plugin`) import `typescript/src/` at build time. Their package builders include the shared implementation in their normal output; they do not carry checked-in copies.

## Build and verify

From the repository root:

```bash
python3.11 -m venv /tmp/mem0-agent-plugins
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

For a TypeScript host, import the shared lifecycle modules directly and keep only native SDK registration in the integration. Do not advertise capture, compaction, or sidekick behavior unless the host exposes the necessary lifecycle seam.
