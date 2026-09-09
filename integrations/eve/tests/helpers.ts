import type { MemoryMessage, MemoryStore, SearchHit } from "../src/store.js";

export function createFakeStore(hits: SearchHit[] = []): MemoryStore & {
  added: Array<{ messages: readonly MemoryMessage[]; userId: string }>;
  searched: Array<{ query: string; userId: string }>;
  deleted: string[];
} {
  const added: Array<{ messages: readonly MemoryMessage[]; userId: string }> = [];
  const searched: Array<{ query: string; userId: string }> = [];
  const deleted: string[] = [];

  return {
    added,
    searched,
    deleted,
    async add(messages, input) {
      added.push({ messages, userId: input.userId });
      return { eventId: "evt_1" };
    },
    async search(query, input) {
      searched.push({ query, userId: input.filters.user_id });
      return { results: hits };
    },
    async delete(memoryId) {
      deleted.push(memoryId);
      return { message: "ok" };
    },
  };
}

export function memoryContext(input?: {
  scopeKey?: string;
  operationId?: string;
  turnInput?: Array<{ role: string; content: unknown }>;
  messages?: Array<{ role: string; content: unknown }>;
}): {
  abortSignal: AbortSignal;
  operationId: string;
  session: { id: string };
  memory: {
    scope: { key: string; namespace: string; value: string };
    slot: string;
  };
  messages: Array<{ role: string; content: unknown }>;
  turn: {
    id: string;
    sequence: number;
    input: Array<{ role: string; content: unknown }>;
  };
} {
  return {
    abortSignal: new AbortController().signal,
    operationId: input?.operationId ?? "op_1",
    session: { id: "sess_1" },
    memory: {
      scope: {
        key: input?.scopeKey ?? "scope_abc",
        namespace: "default",
        value: "user_1",
      },
      slot: "mem0",
    },
    messages: input?.messages ?? [
      { role: "user", content: "I am vegetarian" },
      { role: "assistant", content: "I will remember that." },
    ],
    turn: {
      id: "turn_1",
      sequence: 1,
      input: input?.turnInput ?? [{ role: "user", content: "I am vegetarian" }],
    },
  };
}
