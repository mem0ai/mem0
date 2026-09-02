# Mem0 agent plugins

One shared implementation produces self-contained plugins for Claude Code, Cursor, Codex, Kimi, and Antigravity. Claude Code remains the behavioral source of truth; its sidekick prompt is copied byte-for-byte from `shared/sidekick/prompt.md`.

## Layout

- `core/python/`: capture, recall, scoping, MCP, CLI, and telemetry used by Python hosts.
- `core/typescript/`: formatting, identity, scoping, and telemetry reused by TypeScript integrations.
- `shared/`: the only source for portable skill text and the Claude sidekick prompt.
- `hosts/<name>/`: one descriptor, a payload adapter, and native manifest files.
- `dist/<name>/{native,portable}/`: generated, self-contained artifacts with no symlinks.

Host adapters only normalize the host payload and delegate to the shared core. Keep lifecycle policy and memory behavior out of adapters.

## Build and test

From the repository root:

```bash
python3 -m venv /tmp/mem0-agent-plugins
/tmp/mem0-agent-plugins/bin/pip install -r integrations/agent-plugins/requirements-dev.txt
/tmp/mem0-agent-plugins/bin/python integrations/agent-plugins/scripts/build.py cursor --kind native --output integrations/agent-plugins/dist/cursor/native
/tmp/mem0-agent-plugins/bin/python integrations/agent-plugins/scripts/build.py cursor --kind portable --output integrations/agent-plugins/dist/cursor/portable
/tmp/mem0-agent-plugins/bin/python integrations/agent-plugins/scripts/validate.py integrations/agent-plugins/dist/cursor/portable --kind portable
/tmp/mem0-agent-plugins/bin/python -m pytest integrations/agent-plugins -q
pnpm --dir integrations/agent-plugins/core/typescript test
pnpm --dir integrations/agent-plugins/core/typescript typecheck
```

Replace `cursor` with `claude-code`, `codex`, `kimi`, or `antigravity`.

## Add a Python host

1. Add `hosts/<name>/host.json`, a thin `adapter.py`, and only the manifest files required by that host's official plugin format.
2. Add the smallest native builder in `scripts/build.py`; portable output already comes from the descriptor and shared templates.
3. Add an adapter contract test and build both artifacts. Register the native path in the appropriate marketplace without renaming the plugin.

Do not use symlinks or copy shared logic into a host directory. Add sidekick metadata only when that host documents a native subagent format; do not assume Claude's worktree semantics elsewhere.
