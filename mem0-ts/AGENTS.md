# TypeScript SDK (`mem0-ts/`)

The `mem0ai` package on npm. Hosted client plus self-hosted OSS memory.

## Commands

```bash
pnpm install
pnpm run build              # tsup (CJS + ESM)
pnpm run test               # jest, all tests
pnpm run test:unit          # jest --coverage
pnpm run test:integration   # jest, needs MEM0_API_KEY
pnpm run test:ci            # jest --coverage --ci
pnpm run test:watch
pnpm run typecheck          # tsc --noEmit
```

pnpm only. Never npm, never yarn.

## Conventions

- **Node 20 and 22** are the CI-tested versions.
- **Build:** tsup, dual CJS + ESM output.
- **Formatter:** Prettier. No linter is configured here; `cli/node/` uses Biome and `integrations/vercel-ai-sdk/` uses ESLint, so do not assume a shared setup.
- **Tests:** jest. `cli/node/` and `integrations/openclaw/` use vitest instead.
- **TypeScript strict mode.**
- ES module `import` syntax only. Never `require()`.
- Source files are `snake_case.ts`, tests are `<module>.test.ts`.

Run `pnpm run typecheck` after every change.

## Layout

```
mem0-ts/src/
├── client/          MemoryClient (hosted platform)
└── oss/             Memory (self-hosted)
    ├── llms/
    ├── embeddings/
    ├── vector_stores/
    └── graphs/
```

## Public API

| Export         | Purpose                | Import                                         |
| -------------- | ---------------------- | ---------------------------------------------- |
| `MemoryClient` | Hosted platform client | `import { MemoryClient } from 'mem0ai'`        |
| `Memory`       | Self-hosted OSS memory | `import { Memory } from 'mem0ai/oss'`          |
| Providers      | OSS building blocks    | `import { OpenAIEmbedding } from 'mem0ai/oss'` |

The method surface mirrors the Python SDK: `add`, `search`, `get`, `getAll`, `update`, `delete`, `deleteAll`, `history`. Changing any public signature means updating `docs/` in the same PR.

## Releasing

Tag prefix `ts-v*` triggers `ts-sdk-cd.yml`, which publishes to npm over OIDC. Bump the version in `package.json` first.
