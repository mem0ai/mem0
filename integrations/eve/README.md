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

Until Eve lists Mem0 in the official registry, add the slot file yourself as `agent/memory/mem0.ts`. After the registry PR lands, this becomes:

```bash
eve add memory/mem0
```

## What it does

| Eve hook | Mem0 behavior |
|---|---|
| `recall["turn.started"]` | Semantic search over memories for the locked scope |
| `recall["compaction.completed"]` | Same search after Eve compacting history |
| `capture["turn.completed"]` | Add the completed user/assistant turn |
| `tools()` | `search`, `remember`, `forget` |

Every read and write is partitioned by `memory.scope.key`. The model cannot choose another caller. Replay uses `operationId` as an idempotency key.

If the slot file is named `mem0.ts`, Eve qualifies tools as `mem0__search`, `mem0__remember`, and `mem0__forget`.

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
| `apiKey` | required | String or async getter |
| `host` | `https://api.mem0.ai` | Mem0 Platform host |
| `topK` | `5` | Memories recalled per turn |
| `threshold` | `0.1` | Minimum similarity |
| `rerank` | `false` | Mem0 reranking |
| `infer` | `true` | Extract facts on capture |
| `autoSearch.enabled` | `true` | Recall before each turn |
| `capture.enabled` | `true` | Write after each successful turn |
| `metadata` | `{}` | Extra metadata on captured turns |

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
