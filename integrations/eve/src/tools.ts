import { defineTool } from "eve/tools";
import { z } from "zod";
import type { MemoryStore } from "./store.js";

export interface Mem0ToolOptions {
  readonly topK: number;
  readonly threshold: number;
  readonly rerank: boolean;
  readonly infer: boolean;
}

export function createMem0Tools(
  store: MemoryStore,
  scopeKey: string,
  options: Mem0ToolOptions,
) {
  return {
    search: defineTool({
      description: "Search long-term memories for the current caller.",
      inputSchema: z.object({
        query: z.string().min(1).max(2000),
      }),
      async execute({ query }) {
        const { results } = await store.search(query, {
          userId: scopeKey,
          topK: options.topK,
          threshold: options.threshold,
          rerank: options.rerank,
        });
        return {
          memories: results.map((hit) => ({
            id: hit.id,
            memory: hit.memory,
          })),
        };
      },
    }),
    remember: defineTool({
      description:
        "Save one durable fact or preference about the current caller.",
      inputSchema: z.object({
        text: z.string().min(1).max(4000),
      }),
      async execute({ text }) {
        await store.add([{ role: "user", content: text }], {
          userId: scopeKey,
          infer: options.infer,
          metadata: { source: "eve-tool" },
        });
        return { saved: true };
      },
    }),
    forget: defineTool({
      description: "Delete one memory belonging to the current caller by id.",
      inputSchema: z.object({
        id: z.string().min(1),
      }),
      async execute({ id }) {
        await store.delete(id, scopeKey);
        return { deleted: true };
      },
    }),
  };
}
