# Integrations (`integrations/`)

Agent and editor integrations. Each subdirectory is self-contained: its own `package.json`, lockfile, build, and tests. **There is no shared toolchain.** Check the table before running anything.

| Directory | Package | Build | Lint | Test |
|-----------|---------|-------|------|------|
| `vercel-ai-sdk/` | `@mem0/vercel-ai-provider` | tsup (CJS+ESM) | ESLint + Prettier | jest + vitest (edge/node) |
| `openclaw/` | `@mem0/openclaw-mem0` | tsup (ESM) | none | vitest |
| `claude-code-plugin/` | Claude Code plugin, installs as `mem0@mem0-plugins` (v0.3.0) | none | ruff | pytest |
| `mem0-plugin/` | Cursor / Codex / Kimi / Antigravity / OpenCode plugin (legacy — Claude Code moved to `claude-code-plugin/`) | none | none | pytest |
| `mem0-plugin/.opencode-plugin/` | `@mem0/opencode-plugin` | Bun | none | tsc type-check |
| `pi-agent-plugin/` | `@mem0/pi-agent-plugin` | tsup | none | vitest |
| `deepseek-plugin/` | `@mem0/deepseek-plugin` | tsup (ESM) | none | vitest |
| `n8n-nodes-mem0/` | `@mem0/n8n-nodes-mem0` | tsc | ESLint (n8n-nodes-base) | none |
| `zapier-mem0/` | `@mem0/zapier` | tsc | none | offline unit tests + `zapier validate` |
| `mem0-strands/` | `mem0-strands` (PyPI) | hatch | Ruff + mypy | pytest |

pnpm everywhere except `.opencode-plugin/` (Bun) and `mem0-strands/` (Python: pip / hatch). Never npm, never yarn.

## Commands

```bash
cd integrations/vercel-ai-sdk
pnpm install
pnpm run build           # tsup
pnpm run lint            # eslint
pnpm run type-check      # tsc --noEmit
pnpm run prettier-check
pnpm run test            # jest
pnpm run test:edge       # vitest, edge runtime
pnpm run test:node       # vitest, node runtime

cd integrations/openclaw
pnpm install
pnpm run build           # tsup
pnpm run test            # vitest
```

Run the type check after every TypeScript change: `pnpm run typecheck` or `tsc --noEmit`, whichever the package defines.

## What each one is

- **`vercel-ai-sdk/`** wraps the Vercel AI SDK through a `createMem0` provider. Integrations for AI-SDK repos go through this wrapper, not raw `MemoryClient`.
- **`claude-code-plugin/`** is the Claude Code plugin (v0.3.0, installs as `mem0@mem0-plugins`): local evidence capture via lifecycle hooks, background memory extraction to the Mem0 Platform, a local `search_memories` MCP tool, six `/mem0:*` skills, and the `mem0:sidekick` agent. Pure-stdlib Python — no dependencies to install. Its `core/` + `adapters/claude/` split marks engine vs. harness glue; future per-harness plugins start by copying `core/` and keeping the contract tests verbatim (see its `docs/CONTRACT.md`).
- **`mem0-plugin/`** connects Cursor, Codex, Kimi, Antigravity, and OpenCode to the MCP server at `mcp.mem0.ai` and installs lifecycle hooks for automatic memory capture. Exposes 9 MCP tools: `add_memory`, `search_memories`, `get_memories`, `get_memory`, `update_memory`, `delete_memory`, `delete_all_memories`, `delete_entities`, `list_entities`. The Claude Code plugin moved to [`claude-code-plugin/`](claude-code-plugin/) in v0.3.0 (installs as `mem0@mem0-plugins`); do not run both at the same time.
- **`openclaw/`**, **`pi-agent-plugin/`**, **`deepseek-plugin/`** are editor and agent plugins with the same shape. `deepseek-plugin/` registers Mem0 search/add tools as a native DeepSeek Harness (Cordis) plugin.
- **`n8n-nodes-mem0/`** is an n8n community node: add, search, get, update, delete.
- **`zapier-mem0/`** is a Zapier Platform CLI app: add, search, get, delete. It deploys to Zapier, not npm, so it is **not** in the release router. Deploy it with `gh workflow run zapier-mem0-cd.yml --ref main` (needs the `ZAPIER_DEPLOY_KEY` secret).
- **`mem0-strands/`** is a native Strands `MemoryStore` (Python, published to PyPI as `mem0-strands`). It plugs into the Strands `MemoryManager` for automatic recall and server-side extraction, over the hosted Mem0 platform or self-hosted Mem0 OSS. The package lives under `mem0-strands/python/`.

## Adding an integration

1. Create `integrations/<name>/` and build it there, self-contained.
2. If it publishes to a registry, set `repository.directory: "integrations/<name>"` in `package.json` so npm provenance links to the right subdirectory.
3. Add `.github/workflows/<name>-checks.yml` and `<name>-cd.yml`. Use `integrations/<name>` in the `paths:` trigger, `working-directory`, and `cache-dependency-path`. Register the release tag prefix in the `case` block in `release.yml`, keeping the bare `v*` arm last.
   **Workflow filenames are load-bearing:** npm OIDC trusted publishing is pinned to repository plus workflow filename. Renaming one breaks publishing.
4. Register the CI workflow in `ci-gate.yml`: a path filter under the `changes` job, a call job, and an entry in the gate job's `needs` list.
5. If it is a Claude Code or editor marketplace plugin, register its path in all five `marketplace.json` files: root, `.claude-plugin/`, `.cursor-plugin/`, `.codex-plugin/`, and `.agents/plugins/`.
6. Document it under `docs/integrations/` and add the page to `docs/docs.json` and `docs/llms.txt`.
7. Add rows to the table above and to the CI/CD tables in [`../.github/AGENTS.md`](../.github/AGENTS.md).
