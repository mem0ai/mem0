# @mem0/eve

Mem0 as a first-class [Eve](https://eve.dev/docs/memory) memory provider.

Eve recalls relevant memories before each turn, captures completed turns automatically, and exposes search / remember / forget tools bound to the locked memory scope. Mem0 owns storage, extraction, and retrieval.

```ts
import { defineMemory } from "eve/memory";
import { byPrincipal } from "eve/memory/scope";
import { mem0Provider } from "@mem0/eve";

export default defineMemory({
  description: "Recall and manage durable context for the current user.",
  provider: mem0Provider({
    apiKey: process.env.MEM0_API_KEY!,
  }),
  scope: byPrincipal,
});
```

## Install

```bash
npm install @mem0/eve
```

`eve` is a peer dependency. Get an API key from the [Mem0 dashboard](https://app.mem0.ai/dashboard/api-keys).

Until Eve lists Mem0 in the official registry, add the slot file yourself as `agent/memory/mem0.ts`. `eve add memory/mem0` is not available yet. After the registry PR lands, that command will create the same file.

The live MCP path today is `eve add connection/mem0`. That is a different integration: tools the model may call, not automatic recall/capture.

## What it does

| Eve hook | Mem0 behavior |
|---|---|
| `recall["turn.started"]` | Semantic search over memories for the locked scope |
| `recall["compaction.completed"]` | Same search after Eve compacting history (`turn` may be null) |
| `capture["turn.completed"]` | Add the completed user turn and, when present, this turn's assistant reply |
| `tools()` | `search`, `remember`, `forget` |

Search, capture, remember, and forget are partitioned by `memory.scope.key`. Forget loads the memory first and deletes only when `userId` matches that key.

Capture uses `operationId` for **best-effort** deduplication: an in-process gate plus a durable `metadata.operation_id` lookup. This is not atomic — with `infer: true` a prior write can be a PENDING event whose memory is not yet visible, so a restart during that window (or two concurrent workers) can capture the same turn twice. Eliminating that would require a backend-supported atomic idempotency key.

`remember` returns `{ status: "saved" }` when the write resolves, or `{ status: "queued" }` when the platform accepts it for asynchronous extraction (it becomes searchable a moment later).

If the slot file is named `mem0.ts`, Eve qualifies tools as `mem0__search`, `mem0__remember`, and `mem0__forget`.

A throwing `recall` fails the Eve turn. A throwing `capture` is logged by Eve and does not fail the turn. Tool `execute` errors become failed tool results the model can see.

## Options

```ts
mem0Provider({
  apiKey: process.env.MEM0_API_KEY!,
  host: "https://api.mem0.ai",
  topK: 5,
  threshold: 0.1,
  rerank: false,
  infer: true,
  autoSearch: { enabled: true },
  capture: { enabled: true },
  metadata: { app: "support-agent" },
});
```

| Option | Default | Purpose |
|---|---|---|
| `apiKey` | required without `store` | String or async getter. Function keys are validated on first use. |
| `host` | `https://api.mem0.ai` | Mem0 Platform host (`http:` or `https:` URL) |
| `topK` | `5` | Result count for automatic recall and the `search` tool |
| `threshold` | `0.1` | Minimum similarity for automatic recall and the `search` tool |
| `rerank` | `false` | Mem0 reranking for automatic recall and the `search` tool |
| `infer` | `true` | Extract facts on capture and on `remember` |
| `autoSearch.enabled` | `true` | Recall on `turn.started` and `compaction.completed` |
| `capture.enabled` | `true` | Write after each successful turn |
| `metadata` | `{}` | Extra metadata on captured turns |
| `store` | unset | Test / advanced injection. Replaces the Mem0 client and must honor `userId`. |

## Official registry

Eve already listed Mem0 as an MCP connection. This package is the memory-provider path. After `@mem0/eve` is on npm, open a PR against [vercel/eve](https://github.com/vercel/eve) that adds `memory/mem0` using the files in [`registry/`](./registry). See [`registry/README.md`](./registry/README.md).

## Development

Requires Node.js 24+.

```bash
cd integrations/eve
pnpm install
pnpm test
pnpm typecheck
pnpm build
```
