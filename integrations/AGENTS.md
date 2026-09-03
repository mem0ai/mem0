# Integrations (`integrations/`)

Agent and editor integrations. Most packages are self-contained; coding-agent plugins share the code in `agent-plugin-core/`. Check the table before running anything.

| Directory | Package | Build | Lint | Test |
|-----------|---------|-------|------|------|
| `vercel-ai-sdk/` | `@mem0/vercel-ai-provider` | tsup (CJS+ESM) | ESLint + Prettier | jest + vitest (edge/node) |
| `openclaw/` | `@mem0/openclaw-mem0` | tsup (ESM) | none | vitest |
| `agent-plugin-core/` | Shared Python/TypeScript behavior, skill templates, builds, and conformance | Python build script | ruff + tsc | pytest + node:test |
| `mem0-agent-plugin/` | One portable Agent Plugins v1 package | Python | ruff | shared conformance |
| `claude-code-plugin/`, `cursor-plugin/`, `codex-plugin/`, `kimi-plugin/`, `antigravity-plugin/` | Self-contained native plugins generated from the shared Python core | Python | ruff | pytest |
| `opencode-plugin/` | `@mem0/opencode-plugin` (Bun/TypeScript) | tsup (via Bun) | tsc | bun test |
| `pi-agent-plugin/` | `@mem0/pi-agent-plugin` | tsup | none | vitest |
| `deepseek-plugin/` | `@mem0/deepseek-plugin` | tsup (ESM) | none | vitest |
| `n8n-nodes-mem0/` | `@mem0/n8n-nodes-mem0` | tsc | ESLint (n8n-nodes-base) | none |
| `zapier-mem0/` | `@mem0/zapier` | tsc | none | offline unit tests + `zapier validate` |
| `mem0-strands/` | `mem0-strands` (PyPI) | hatch | Ruff + mypy | pytest |

pnpm for TypeScript packages except `opencode-plugin/` (Bun). `mem0-strands/` uses Python/pip/hatch. Never npm or yarn.

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
- **`agent-plugin-core/`** owns the shared Python memory runtime, TypeScript lifecycle utilities, skill templates, builds, and conformance runner. Claude Code is the behavioral source of truth. Native manifests and adapters live in sibling plugin directories; do not hand-edit their generated `core/` or `skills/` trees. Build and validation details are in [`agent-plugin-core/README.md`](agent-plugin-core/README.md).
- **`opencode-plugin/`** is a Bun/TypeScript plugin for OpenCode (`@mem0/opencode-plugin` on npm). It registers Mem0 memory tools as an OpenCode plugin with its own skills and telemetry.
- **`openclaw/`**, **`pi-agent-plugin/`**, **`deepseek-plugin/`** are editor and agent plugins with the same shape. `deepseek-plugin/` registers Mem0 search/add tools as a native DeepSeek Harness (Cordis) plugin.
- **`n8n-nodes-mem0/`** is an n8n community node: add, search, get, update, delete.
- **`zapier-mem0/`** is a Zapier Platform CLI app: add, search, get, delete. It deploys to Zapier, not npm, so it is **not** in the release router. Deploy it with `gh workflow run zapier-mem0-cd.yml --ref main` (needs the `ZAPIER_DEPLOY_KEY` secret).
- **`mem0-strands/`** is a native Strands `MemoryStore` (Python, published to PyPI as `mem0-strands`). It plugs into the Strands `MemoryManager` for automatic recall and server-side extraction, over the hosted Mem0 platform or self-hosted Mem0 OSS. The package lives under `mem0-strands/python/`.

## Adding an integration

1. For a native coding-agent host, add `integrations/<name>-plugin/` with `plugin-build.json`, its manifest, and a thin adapter, then generate its shared runtime. Portable clients use the single `mem0-agent-plugin/` package. Independent TypeScript integrations stay self-contained and import shared lifecycle behavior from `agent-plugin-core/typescript/`.
2. If it publishes to a registry, set `repository.directory: "integrations/<name>"` in `package.json` so npm provenance links to the right subdirectory.
3. Add `.github/workflows/<name>-checks.yml` and `<name>-cd.yml`. Use `integrations/<name>` in the `paths:` trigger, `working-directory`, and `cache-dependency-path`. Register the release tag prefix in the `case` block in `release.yml`, keeping the bare `v*` arm last.
   **Workflow filenames are load-bearing:** npm OIDC trusted publishing is pinned to repository plus workflow filename. Renaming one breaks publishing.
4. Register the CI workflow in `ci-gate.yml`: a path filter under the `changes` job, a call job, and an entry in the gate job's `needs` list.
5. If it is a Claude Code or editor marketplace plugin, register the generated native bundle path in the applicable marketplace files. Preserve the existing public plugin name.
6. Document it under `docs/integrations/` and add the page to `docs/docs.json` and `docs/llms.txt`.
7. Add rows to the table above and to the CI/CD tables in [`../.github/AGENTS.md`](../.github/AGENTS.md).
