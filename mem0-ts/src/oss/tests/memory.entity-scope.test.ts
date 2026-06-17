/**
 * Entity linking scope isolation tests.
 *
 * Entity-store search filters are provider-dependent, so the merge decision
 * must verify that the returned entity payload belongs to the current
 * user/agent/run scope before appending linkedMemoryIds.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import type { MemoryConfig, VectorStoreResult } from "../src/types";

jest.setTimeout(15000);

jest.mock("../src/embeddings/google", () => ({
  GoogleEmbedder: jest.fn(),
}));
jest.mock("../src/llms/google", () => ({
  GoogleLLM: jest.fn(),
}));

jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest.fn().mockResolvedValue(
      JSON.stringify({
        memory: [
          {
            id: "0",
            text: "I met Alice Smith yesterday",
            attributed_to: "user",
          },
        ],
      }),
    ),
  })),
}));

const mockEmbedding = new Array(1536).fill(0.1);
jest.mock("../src/embeddings/openai", () => ({
  OpenAIEmbedder: jest.fn().mockImplementation(() => ({
    embed: jest.fn().mockResolvedValue(mockEmbedding),
    embedBatch: jest
      .fn()
      .mockImplementation((texts: string[]) =>
        Promise.resolve(texts.map(() => mockEmbedding)),
      ),
    embeddingDims: 1536,
  })),
}));

function createMemory(overrides: Partial<MemoryConfig> = {}): Memory {
  return new Memory({
    version: "v1.1",
    embedder: {
      provider: "openai",
      config: { apiKey: "test-key", model: "text-embedding-3-small" },
    },
    vectorStore: {
      provider: "memory",
      config: {
        collectionName: `test-entity-scope-${Date.now()}-${Math.random()}`,
        dimension: 1536,
        dbPath: ":memory:",
      },
    },
    llm: {
      provider: "openai",
      config: { apiKey: "test-key", model: "gpt-5-mini" },
    },
    historyDbPath: ":memory:",
    ...overrides,
  });
}

function makeEntityMatch(payload: Record<string, any>): VectorStoreResult {
  return {
    id: "entity-u1",
    score: 0.99,
    payload: {
      data: "Alice Smith yesterday",
      entityType: "PROPER",
      linkedMemoryIds: ["mem-u1"],
      ...payload,
    },
  };
}

describe("Memory entity linking scope isolation", () => {
  let memory: Memory;

  beforeEach(() => {
    memory = createMemory();
  });

  afterEach(async () => {
    await memory.reset();
  });

  it("inserts a new entity instead of merging a single-memory match from another user scope", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = {
      search: jest.fn().mockResolvedValue([makeEntityMatch({ user_id: "u1" })]),
      update: jest.fn().mockResolvedValue(undefined),
      insert: jest.fn().mockResolvedValue(undefined),
      deleteCol: jest.fn().mockResolvedValue(undefined),
    };
    m._entityStore = mockEntityStore;

    await m._linkEntitiesForMemory("mem-u2", "I met Alice Smith yesterday", {
      user_id: "u2",
    });

    expect(mockEntityStore.update).not.toHaveBeenCalled();

    const insertedPayloads = mockEntityStore.insert.mock.calls.flatMap(
      (call: any[]) => call[2],
    );
    expect(insertedPayloads).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          data: "Alice Smith yesterday",
          user_id: "u2",
          linkedMemoryIds: ["mem-u2"],
        }),
      ]),
    );
  });

  it("inserts a new entity instead of merging a batch add match from another user scope", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = {
      search: jest.fn().mockResolvedValue([makeEntityMatch({ user_id: "u1" })]),
      update: jest.fn().mockResolvedValue(undefined),
      insert: jest.fn().mockResolvedValue(undefined),
      deleteCol: jest.fn().mockResolvedValue(undefined),
    };
    m._entityStore = mockEntityStore;
    m.vectorStore.search = jest.fn().mockResolvedValue([]);

    await memory.add("I met Alice Smith yesterday", { userId: "u2" });

    expect(mockEntityStore.update).not.toHaveBeenCalled();

    const insertedPayloads = mockEntityStore.insert.mock.calls.flatMap(
      (call: any[]) => call[2],
    );
    expect(insertedPayloads).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          data: "Alice Smith yesterday",
          user_id: "u2",
        }),
      ]),
    );
  });
});
