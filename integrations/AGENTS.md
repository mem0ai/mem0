# Integrations (`integrations/`)

Agent and editor integrations. Most packages are self-contained; coding-agent plugins share the code in `agent-plugin-core/`. Check the table before running anything.

| Directory | Package | Build | Lint | Test |
|-----------|---------|-------|------|------|
| `vercel-ai-sdk/` | `@mem0/vercel-ai-provider` | tsup (CJS+ESM) | ESLint + Prettier | jest + vitest (edge/node) |
| `openclaw/` | `@mem0/openclaw-mem0` | tsup (ESM) | none | vitest |
| `hermes-plugin-mem0/` | Standalone Hermes memory provider | none | ruff + isort | pytest (see package README); real-host smoke |
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

## Surface attribution

Every integration tells the Mem0 platform which surface it is. Three headers,
and the rules on them are what keep one layer from erasing another:

| Header | Carries | Rule |
|--------|---------|------|
| `X-Mem0-Source` | one canonical source value | **set-once** — write only if absent |
| `X-Application` | the host app it runs inside | **set-once** — write only if absent |
| `X-Mem0-Client` | `name/version`, outermost first | **append-only** — add yourself, never replace |

Set-once means check-then-set, never assignment. An integration that wraps the
SDK is the outermost layer and sets the source; the SDK underneath defers to it.
Assignment is exactly how every agent plugin came to be indistinguishable from
every other one at the platform.

How to declare it from an integration, in order of preference:

1. Send the headers yourself, if you make the HTTP call directly.
2. Pass `source` in the call options, if you go through an SDK.
3. Set `MEM0_SOURCE` / `MEM0_APPLICATION` / `MEM0_CLIENT_STACK` in the
   environment before constructing the client. The SDKs read these and defer to
   anything already present.

Append-only applies where a stack can actually form: an SDK handed a client that
already carries `X-Mem0-Client` appends itself rather than replacing. An SDK
constructed with no outer context simply reports itself, which is correct — it
is the outermost layer in that process.

The backend recognizes a fixed list of source values and buckets everything else
into `OTHERS`. A new value has to land in the platform's `EventSource` enum, so
do not invent one without that change going in too.

`X-Application` is allowlisted the same way, and this one has a rule of its own:
**omit the header when you do not know the host.** A value outside the allowlist
is discarded server-side, so guessing produces an event that claims an
attribution we do not actually have. The portable bundle is the case that
matters. It runs in whatever editor a user drops it into, so its build leaves
`PLATFORM_APPLICATION` empty and `memory_core` sends no header at all, while the
native bundles each name the host they were generated for. If you add a build
target, decide which of those two it is.

## Adding an integration

1. For a native coding-agent host, add `integrations/<name>-plugin/` with `plugin-build.json`, its manifest, and a thin adapter, then generate its shared runtime. Portable clients use the single `mem0-agent-plugin/` package. Independent TypeScript integrations stay self-contained and import shared lifecycle behavior from `agent-plugin-core/typescript/`.
2. If it publishes to a registry, set `repository.directory: "integrations/<name>"` in `package.json` so npm provenance links to the right subdirectory.
3. Add `.github/workflows/<name>-checks.yml` and `<name>-cd.yml`. Use `integrations/<name>` in the `paths:` trigger, `working-directory`, and `cache-dependency-path`. Register the release tag prefix in the `case` block in `release.yml`, keeping the bare `v*` arm last.
   **Workflow filenames are load-bearing:** npm OIDC trusted publishing is pinned to repository plus workflow filename. Renaming one breaks publishing.
4. Register the CI workflow in `ci-gate.yml`: a path filter under the `changes` job, a call job, and an entry in the gate job's `needs` list.
5. If it is a Claude Code or editor marketplace plugin, register the generated native bundle path in the applicable marketplace files. Preserve the existing public plugin name.
6. Document it under `docs/integrations/` and add the page to `docs/docs.json` and `docs/llms.txt`.
7. Add rows to the table above and to the CI/CD tables in [`../.github/AGENTS.md`](../.github/AGENTS.md).
8. Send the three headers in [Surface attribution](#surface-attribution), and land the matching `EventSource` value on the platform in the same week. Until it exists, your traffic reports as `OTHERS`.
