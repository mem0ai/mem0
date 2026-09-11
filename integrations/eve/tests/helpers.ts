import type {
  AddMemoryInput,
  MemoryMessage,
  MemoryRecord,
  MemoryStore,
  SearchHit,
  SearchMemoryInput,
} from "../src/store.js";

export type FakeHit = SearchHit & {
  readonly userId?: string;
  readonly metadata?: Readonly<Record<string, unknown>>;
};

export type FakeAdd = {
  messages: readonly MemoryMessage[];
  userId: string;
  infer: boolean;
  metadata: Readonly<Record<string, unknown>>;
};

export type FakeSearch = SearchMemoryInput & {
  query: string;
};

export function createFakeStore(
  hits: FakeHit[] = [],
  options: { pendingWrites?: boolean } = {},
): MemoryStore & {
  added: FakeAdd[];
  searched: FakeSearch[];
  deleted: string[];
  records: MemoryRecord[];
} {
  const added: FakeAdd[] = [];
  const searched: FakeSearch[] = [];
  const deleted: string[] = [];
  const records: MemoryRecord[] = hits.map((hit) => ({
    id: hit.id,
    userId: hit.userId ?? "scope_abc",
    metadata: hit.metadata ?? {},
  }));

  return {
    added,
    searched,
    deleted,
    records,
    async add(messages, input) {
      added.push({
        messages,
        userId: input.userId,
        infer: input.infer,
        metadata: input.metadata,
      });
      // Model Mem0's async extraction: a pending write is accepted but its
      // memory is not yet visible to listByMetadata/get, so it cannot dedupe a
      // replay. A resolved write becomes immediately visible.
      if (options.pendingWrites) {
        return { status: "queued" as const, eventId: `evt_${added.length}` };
      }
      records.push({
        id: `mem_added_${added.length}`,
        userId: input.userId,
        metadata: input.metadata,
      });
      return { status: "completed" as const };
    },
    async search(query, input) {
      searched.push({ query, ...input });
      return {
        results: hits.filter((hit) => (hit.userId ?? "scope_abc") === input.userId),
      };
    },
    async get(memoryId) {
      return records.find((record) => record.id === memoryId) ?? null;
    },
    async listByMetadata({ userId, metadata }) {
      return records.filter((record) => {
        if (record.userId !== userId) {
          return false;
        }
        return Object.entries(metadata).every(
          ([key, value]) => record.metadata[key] === value,
        );
      });
    },
    async delete(memoryId, userId) {
      const record = records.find((item) => item.id === memoryId);
      if (!record || record.userId !== userId) {
        throw new Error("Memory not found");
      }
      deleted.push(memoryId);
    },
  };
}

export function memoryContext(input?: {
  scopeKey?: string;
  operationId?: string;
  aborted?: boolean;
  turn?:
    | {
        id?: string;
        sequence?: number;
        input: Array<{ role: string; content: unknown }>;
      }
    | null;
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
  } | null;
} {
  const controller = new AbortController();
  if (input?.aborted) {
    controller.abort();
  }

  const turnInput =
    input?.turn === null
      ? undefined
      : (input?.turn?.input ??
        input?.turnInput ?? [{ role: "user", content: "I am vegetarian" }]);

  return {
    abortSignal: controller.signal,
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
    turn:
      input?.turn === null
        ? null
        : {
            id: input?.turn?.id ?? "turn_1",
            sequence: input?.turn?.sequence ?? 1,
            input: turnInput ?? [{ role: "user", content: "I am vegetarian" }],
          },
  };
}
