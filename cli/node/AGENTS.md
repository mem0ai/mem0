# Node CLI (`cli/node/`)

The `@mem0/cli` package on npm. Commander-based, entry point `mem0`.

## Commands

```bash
pnpm install
pnpm run build        # tsup (ESM)
pnpm run lint         # biome check src/
pnpm run lint:fix     # biome check --write src/
pnpm run typecheck    # tsc --noEmit
pnpm run test         # vitest run
pnpm run test:watch
pnpm run dev          # tsx src/index.ts
```

pnpm only. Never npm, never yarn.

## Conventions

> **Biome, not ESLint. vitest, not jest.** `mem0-ts/` uses Prettier + jest and
> `integrations/vercel-ai-sdk/` uses ESLint + jest. Running those tools here produces
> spurious diffs. Every toolchain in this repo is per-package.

- **Node 18+** required.
- **Build:** tsup, ESM output only.
- **Linter and formatter:** Biome, configured in `biome.json`.
- **Tests:** vitest.
- **TypeScript strict mode.** ES module `import` syntax only, never `require()`.

Run `pnpm run typecheck` after every change.

## Dependencies

Commander + Chalk + ora + cli-table3, and `mem0ai` (npm) for API calls.

## CI and release

- CI: `cli-node-ci.yml`, Biome + tsc + vitest + tsup build on Node 20 and 22.
- Release: tag prefix `cli-node-v*` dispatches `cli-node-cd.yml`, publishing to npm over OIDC.
