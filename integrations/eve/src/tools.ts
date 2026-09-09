import { defineTool } from "eve/tools";
import { z } from "zod";
import type { MemoryStore } from "./store.js";

export function createMem0Tools(store: MemoryStore, scopeKey: string) {
  return {
    search: defineTool({
      description: "Search long-term memories for the current caller.",
      inputSchema: z.object({
        query: z.string().min(1).max(2000),
      }),
      async execute({ query }) {
        const { results } = await store.search(query, {
          filters: { user_id: scopeKey },
          topK: 8,
          threshold: 0.1,
          rerank: false,
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
          infer: true,
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
        await store.delete(id);
        return { deleted: true };
      },
    }),
  };
}
