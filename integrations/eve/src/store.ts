import type { Mem0ApiKey } from "./options.js";
import { isNotFoundError } from "./errors.js";

export type MemoryRole = "user" | "assistant";

export interface MemoryMessage {
  readonly role: MemoryRole;
  readonly content: string;
}

export interface SearchHit {
  readonly id: string;
  readonly memory: string;
}

export interface MemoryRecord {
  readonly id: string;
  readonly userId: string;
  readonly metadata: Readonly<Record<string, unknown>>;
}

export type StoreMetadata = Readonly<Record<string, string | number | boolean>>;

export interface AddMemoryInput {
  readonly userId: string;
  readonly infer: boolean;
  readonly metadata: StoreMetadata;
}

export interface SearchMemoryInput {
  readonly userId: string;
  readonly topK: number;
  readonly threshold: number;
  readonly rerank: boolean;
}

export interface MemoryStore {
  add(messages: readonly MemoryMessage[], input: AddMemoryInput): Promise<void>;
  search(query: string, input: SearchMemoryInput): Promise<{ results: readonly SearchHit[] }>;
  get(memoryId: string): Promise<MemoryRecord | null>;
  listByMetadata(input: {
    readonly userId: string;
    readonly metadata: Readonly<Record<string, string>>;
  }): Promise<readonly MemoryRecord[]>;
  delete(memoryId: string, userId: string): Promise<void>;
}

export function parseSearchHit(item: unknown): SearchHit | null {
  if (!item || typeof item !== "object") {
    return null;
  }
  const record = item as Record<string, unknown>;
  const nested =
    record.data && typeof record.data === "object"
      ? (record.data as Record<string, unknown>)
      : undefined;
  const idValue = record.id ?? record.memory_id ?? nested?.id;
  const id =
    typeof idValue === "string"
      ? idValue.trim()
      : typeof idValue === "number"
        ? String(idValue)
        : "";
  const memoryValue =
    record.memory ?? record.text ?? nested?.memory ?? nested?.text;
  const memory = typeof memoryValue === "string" ? memoryValue : "";
  if (id.length === 0 || memory.trim().length === 0) {
    return null;
  }
  return { id, memory };
}

export function parseMemoryRecord(item: unknown): MemoryRecord | null {
  if (!item || typeof item !== "object") {
    return null;
  }
  const record = item as Record<string, unknown>;
  const idValue = record.id ?? record.memory_id;
  const id = typeof idValue === "string" ? idValue.trim() : "";
  const userIdValue = record.userId ?? record.user_id;
  const userId = typeof userIdValue === "string" ? userIdValue : "";
  if (id.length === 0 || userId.length === 0) {
    return null;
  }
  const metadata =
    record.metadata && typeof record.metadata === "object"
      ? (record.metadata as Record<string, unknown>)
      : {};
  return { id, userId, metadata };
}

function asItemList(response: unknown, operation: string): unknown[] {
  if (Array.isArray(response)) {
    return response;
  }
  if (response && typeof response === "object") {
    const record = response as Record<string, unknown>;
    const raw = record.results ?? record.memories;
    if (Array.isArray(raw)) {
      return raw;
    }
  }
  throw new Error(`Mem0 ${operation} returned an unexpected response shape`);
}

export async function resolveApiKey(apiKey: Mem0ApiKey): Promise<string> {
  const value = typeof apiKey === "function" ? await apiKey() : apiKey;
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    throw new Error("Mem0 API key cannot be empty");
  }
  return trimmed;
}

export function createLazyStore(factory: () => Promise<MemoryStore>) {
  let pending: Promise<MemoryStore> | undefined;

  return async (): Promise<MemoryStore> => {
    if (!pending) {
      pending = factory().catch((error: unknown) => {
        pending = undefined;
        throw error;
      });
    }
    return pending;
  };
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

  const store: MemoryStore = {
    async add(messages, options) {
      await client.add([...messages], {
        userId: options.userId,
        infer: options.infer,
        metadata: { ...options.metadata },
      });
    },
    async search(query, options) {
      const response = await client.search(query, {
        filters: { user_id: options.userId },
        topK: options.topK,
        threshold: options.threshold,
        rerank: options.rerank,
      });
      return {
        results: asItemList(response, "search").flatMap((item) => {
          const hit = parseSearchHit(item);
          return hit ? [hit] : [];
        }),
      };
    },
    async get(memoryId) {
      try {
        return parseMemoryRecord(await client.get(memoryId));
      } catch (error) {
        if (isNotFoundError(error)) {
          return null;
        }
        throw error;
      }
    },
    async listByMetadata({ userId, metadata }) {
      const response = await client.getAll({
        filters: {
          AND: [{ user_id: userId }, { metadata }],
        },
        pageSize: 5,
      });
      return asItemList(response, "getAll").flatMap((item) => {
        const record = parseMemoryRecord(item);
        return record && record.userId === userId ? [record] : [];
      });
    },
    async delete(memoryId, userId) {
      const record = await store.get(memoryId);
      if (!record || record.userId !== userId) {
        throw new Error("Memory not found");
      }
      await client.delete(memoryId);
    },
  };
  return store;
}
