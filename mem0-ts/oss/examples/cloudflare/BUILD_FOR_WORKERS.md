# Proposal: Build a Workers / Browser-friendly mem0 bundle

Goal

Provide a pure-JS / WebAssembly-friendly build of mem0 that can run in Cloudflare Workers and other edge runtimes. This avoids Node native bindings (SQLite native modules, fs, process-bound APIs) and prototype chain issues caused by certain libraries.

High-level approach

1. Create a new entrypoint: `src/worker-entry.ts` (or `src/browser-entry.ts`) that re-exports only the portable parts of the SDK. This entrypoint must not import any files that depend on native modules (sqlite3) or Node-only APIs.

2. Use a bundler that targets the web/worker: esbuild or rollup (or tsup configured to produce browser builds). The bundler should:
   - Replace or stub Node shims (fs, path, process) with browser-safe alternatives.
   - Mark native modules as external or provide WASM alternatives (for sqlite use sql.js or wasm-sqlite).
   - Produce an ESM output suitable for Workers.

3. Conditional exports in package.json:
   - Add an export like `"./worker": {"import": "./dist/worker/index.mjs", "types": "./dist/worker/index.d.ts"}` so consumers can explicitly import the worker-safe build.
   - Optionally set a `browser` field for bundlers that respect it.

4. SQLite via WASM:
   - Replace native `sqlite3` with a WASM alternative such as `sql.js` or `better-sqlite3-wasm` in the worker build.
   - Provide an adapter layer under `src/storage/wasm-sqlite-adapter.ts` that implements the same high-level API as the native manager but delegates to WASM.

5. Prototype chain issues
   - Ensure exported objects are plain objects or classes that extend Object properly. Avoid mixing prototypes from different realms (for example by using Object.create(null) sparingly).
   - Where third-party libraries change prototype chains, rewrap objects before sending across the worker boundary.

6. Tests and CI
   - Add a CI job (GitHub Actions) that runs a build for the worker target and runs a small smoke test using Node's `node --experimental-worker` or a local Cloudflare Wrangler test runner.
   - Add tests that import the `./worker` bundle and run a few core functions (create/query memory) using an in-memory WASM-backed store.

Minimal required changes in the repo

- Add `src/worker-entry.ts` that only pulls portable modules.
- Add bundler config (esbuild or tsup) to emit `dist/worker/*.mjs` + types.
- Implement a WASM-backed SQLite adapter under `src/storage/`.
- Add package.json exports for the worker build and update README/docs.

Notes and tradeoffs

- Maintaining two build targets increases project complexity. Keep the worker entry small and well-documented.
- Some vector DB integrations (pgvector, redis) or certain native drivers will remain server-only. The worker build should clearly document unsupported features.

Example import for consumers

import mem0 from 'mem0/worker';

This will load the worker-safe ESM bundle.
