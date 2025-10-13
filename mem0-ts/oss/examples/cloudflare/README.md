# mem0 Cloudflare Worker example

This example shows how to use mem0 as an HTTP API client from a Cloudflare Worker (or other edge runtimes).

## Summary

- The Worker forwards requests from an edge environment to a mem0 HTTP API endpoint.
- It uses a tiny fetch-based client wrapper that avoids Node.js-only APIs (fs, native sqlite, streams).
- This example does NOT recompile the full SDK to WebAssembly. Instead it demonstrates the recommended pattern: run mem0 on a server and call it from Workers via HTTP.

## Files

- `worker.ts` - example Cloudflare Worker code using the fetch client.
- `mem0-worker-client.ts` - a minimal, portable client wrapper that uses fetch and plain objects.

## Limitations and notes

- If you need the full SDK in the Worker (in-process memory, SQLite access), you must build a WebAssembly or pure-JS variant of the parts that rely on native bindings. That requires changes to the SDK build and possibly shipping a separate entrypoint in `package.json` (e.g. `browser`/`worker` fields) that excludes native modules.
- This repository provides an example of the recommended approach (API client + server) which is the simplest path for production edge usage.

## Quick start (Cloudflare Wrangler)

1. Install Wrangler and log in.
2. Create a new Worker project and copy `worker.ts` and `mem0-worker-client.ts` into it.
3. Set secrets/environment variables for the mem0 API URL and API key in Wrangler.
4. Deploy.

## Example Environment Variables

- `MEM0_API_BASE=https://mem0.example.com`
- MEM0_API_KEY=sk_...

See the `worker.ts` for usage details.
