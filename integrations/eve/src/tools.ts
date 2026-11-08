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
        "Save one durable fact or preference about the current caller. On the " +
        "hosted platform the write is queued for extraction and may take a " +
        "moment to become searchable; a `queued` status means accepted, not yet " +
        "stored. Do not claim the fact is saved when the status is queued.",
      inputSchema: z.object({
        text: z.string().min(1).max(4000),
      }),
      async execute({ text }) {
        const result = await store.add([{ role: "user", content: text }], {
          userId: scopeKey,
          infer: options.infer,
          metadata: { source: "eve-tool" },
        });
        // Report the true write state. With infer:true the platform returns a
        // PENDING event, so promising "saved" would let the model tell the user
        // a fact is stored when only the request was queued. Surface the eventId
        // so the write can be correlated/confirmed rather than left a dead end.
        return result.status === "queued"
          ? {
              status: "queued" as const,
              ...(result.eventId ? { eventId: result.eventId } : {}),
            }
          : { status: "saved" as const };
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
