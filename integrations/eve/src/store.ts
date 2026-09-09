import type { Mem0ApiKey } from "./options.js";

export type MemoryRole = "user" | "assistant";

export interface MemoryMessage {
  readonly role: MemoryRole;
  readonly content: string;
}

export interface SearchHit {
  readonly id: string;
  readonly memory: string;
}

export interface AddMemoryInput {
  readonly userId: string;
  readonly infer: boolean;
  readonly metadata: Readonly<Record<string, unknown>>;
}

export interface SearchMemoryInput {
  readonly filters: {
    readonly user_id: string;
  };
  readonly topK: number;
  readonly threshold: number;
  readonly rerank: boolean;
}

export interface MemoryStore {
  add(messages: readonly MemoryMessage[], input: AddMemoryInput): Promise<unknown>;
  search(query: string, input: SearchMemoryInput): Promise<{ results: readonly SearchHit[] }>;
  delete(memoryId: string): Promise<unknown>;
}

export async function resolveApiKey(apiKey: Mem0ApiKey): Promise<string> {
  const value = typeof apiKey === "function" ? await apiKey() : apiKey;
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    throw new Error("Mem0 API key cannot be empty");
  }
  return trimmed;
}

export async function createMem0Store(input: {
  apiKey: Mem0ApiKey;
  host: string;
}): Promise<MemoryStore> {
  const MemoryClient = (await import("mem0ai")).default;
  const client = new MemoryClient({
    apiKey: await resolveApiKey(input.apiKey),
    host: input.host,
  });

  return {
    async add(messages, options) {
      return client.add([...messages], {
        userId: options.userId,
        infer: options.infer,
        metadata: { ...options.metadata },
      });
    },
    async search(query, options) {
      const response = await client.search(query, {
        filters: options.filters,
        topK: options.topK,
        threshold: options.threshold,
        rerank: options.rerank,
      });
      const results = Array.isArray(response?.results) ? response.results : [];
      return {
        results: results.flatMap((item) => {
          const id = typeof item.id === "string" ? item.id : "";
          const memory = typeof item.memory === "string" ? item.memory : "";
          return id && memory ? [{ id, memory }] : [];
        }),
      };
    },
    async delete(memoryId) {
      return client.delete(memoryId);
    },
  };
}
