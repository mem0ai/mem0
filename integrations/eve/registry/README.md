# Eve registry contribution

These files are the Mem0 side of `eve add memory/mem0`. They are not published in the npm tarball. Copy them into a PR against [vercel/eve](https://github.com/vercel/eve) after `@mem0/eve` is on npm.

Supermemory's version of this change is [vercel/eve#2775](https://github.com/vercel/eve/pull/2775). Use that PR as the catalog/shape reference.

## What the Eve PR should do

1. Add a `kind: "memory"` catalog item named `mem0`.
2. Install `@mem0/eve` and declare `MEM0_API_KEY`.
3. Write `agent/memory/mem0.ts` from [`mem0.ts`](./mem0.ts).
4. List Mem0 on [eve.dev/docs/memory](https://eve.dev/docs/memory) next to Supermemory and Upstash.

[`item.json`](./item.json) is the shadcn-registry shape Eve uses for `eve add`. Adapt field names to Eve's current catalog schema if it has moved since this was written.

## Suggested install command

```bash
eve add memory/mem0
```

## Suggested docs snippet

```ts
import { mem0Provider } from "@mem0/eve";
import { defineMemory } from "eve/memory";
import { byPrincipal } from "eve/memory/scope";

export default defineMemory({
  description: "Recall and manage durable context for the current user.",
  provider: mem0Provider({
    apiKey: process.env.MEM0_API_KEY!,
  }),
  scope: byPrincipal,
});
```
