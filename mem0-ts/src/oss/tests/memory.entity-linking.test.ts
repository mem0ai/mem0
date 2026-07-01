/**
 * Entity linking scope isolation tests.
 *
 * Regression coverage for cross-scope entity candidates returned by vector
 * stores despite scoped search filters.
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

jest.mock("../src/utils/entity_extraction", () => ({
  extractEntities: jest.fn(() => [{ text: "OpenClaw", type: "ORG" }]),
  extractEntitiesBatch: jest.fn((texts: string[]) =>
    texts.map(() => [{ text: "OpenClaw", type: "ORG" }]),
  ),
}));

jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest.fn().mockResolvedValue(
      JSON.stringify({
        memory: [
          {
            id: "0",
            text: "OpenClaw editor integration is enabled",
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
        collectionName: `test-entity-linking-${Date.now()}-${Math.random()}`,
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

function crossScopeEntity(
  payload: Record<string, any> = { user_id: "user-a" },
): VectorStoreResult {
  return {
    id: "entity-user-a",
    score: 0.99,
    payload: {
      data: "OpenClaw",
      entityType: "ORG",
      linkedMemoryIds: ["memory-user-a"],
      ...payload,
    },
  };
}

function makeEntityStore({
  listMatches = [],
  searchMatches = [crossScopeEntity()],
}: {
  listMatches?: VectorStoreResult[];
  searchMatches?: VectorStoreResult[];
} = {}) {
  return {
    list: jest.fn().mockResolvedValue([listMatches, listMatches.length]),
    search: jest.fn().mockResolvedValue(searchMatches),
    insert: jest.fn().mockResolvedValue(undefined),
    update: jest.fn().mockResolvedValue(undefined),
    deleteCol: jest.fn().mockResolvedValue(undefined),
    initialize: jest.fn().mockResolvedValue(undefined),
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

  it("does not merge single-memory entities into a returned candidate from another user scope", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = makeEntityStore();
    m._entityStore = mockEntityStore;

    await m._linkEntitiesForMemory("memory-user-b", "OpenClaw enabled", {
      user_id: "user-b",
    });

    expect(mockEntityStore.search).toHaveBeenCalledWith(expect.any(Array), 10, {
      user_id: "user-b",
    });
    expect(mockEntityStore.update).not.toHaveBeenCalled();
    expect(mockEntityStore.insert).toHaveBeenCalledTimes(1);
    expect(mockEntityStore.insert.mock.calls[0][2][0]).toMatchObject({
      data: "OpenClaw",
      entityType: "ORG",
      user_id: "user-b",
      linkedMemoryIds: ["memory-user-b"],
    });
  });

  it("uses the first in-scope semantic match when an out-of-scope candidate ranks first", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = makeEntityStore({
      searchMatches: [
        crossScopeEntity({
          user_id: "user-a",
          linkedMemoryIds: ["memory-user-a"],
        }),
        {
          ...crossScopeEntity({
            user_id: "user-b",
            linkedMemoryIds: ["memory-user-c"],
          }),
          id: "entity-user-b",
          score: 0.97,
        },
      ],
    });
    m._entityStore = mockEntityStore;

    await m._linkEntitiesForMemory("memory-user-b", "OpenClaw enabled", {
      user_id: "user-b",
    });

    expect(mockEntityStore.search).toHaveBeenCalledWith(expect.any(Array), 10, {
      user_id: "user-b",
    });
    expect(mockEntityStore.insert).not.toHaveBeenCalled();
    expect(mockEntityStore.update).toHaveBeenCalledWith(
      "entity-user-b",
      expect.any(Array),
      expect.objectContaining({
        user_id: "user-b",
        linkedMemoryIds: ["memory-user-b", "memory-user-c"],
      }),
    );
  });

  it("uses the highest-scoring in-scope semantic match when results are unordered", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = makeEntityStore({
      searchMatches: [
        {
          ...crossScopeEntity({
            user_id: "user-b",
            linkedMemoryIds: ["memory-user-low"],
          }),
          id: "entity-user-low",
          score: 0.96,
        },
        {
          ...crossScopeEntity({
            user_id: "user-b",
            linkedMemoryIds: ["memory-user-high"],
          }),
          id: "entity-user-high",
          score: 0.99,
        },
      ],
    });
    m._entityStore = mockEntityStore;

    await m._linkEntitiesForMemory("memory-user-b", "OpenClaw enabled", {
      user_id: "user-b",
    });

    expect(mockEntityStore.insert).not.toHaveBeenCalled();
    expect(mockEntityStore.update).toHaveBeenCalledWith(
      "entity-user-high",
      expect.any(Array),
      expect.objectContaining({
        user_id: "user-b",
        linkedMemoryIds: ["memory-user-b", "memory-user-high"],
      }),
    );
  });

  it("continues to merge single-memory entities into an in-scope semantic match", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = makeEntityStore({
      searchMatches: [
        crossScopeEntity({
          user_id: "user-b",
          linkedMemoryIds: ["memory-user-a"],
        }),
      ],
    });
    m._entityStore = mockEntityStore;

    await m._linkEntitiesForMemory("memory-user-b", "OpenClaw enabled", {
      user_id: "user-b",
    });

    expect(mockEntityStore.insert).not.toHaveBeenCalled();
    expect(mockEntityStore.update).toHaveBeenCalledTimes(1);
    expect(mockEntityStore.update).toHaveBeenCalledWith(
      "entity-user-a",
      expect.any(Array),
      expect.objectContaining({
        data: "OpenClaw",
        entityType: "ORG",
        user_id: "user-b",
        linkedMemoryIds: ["memory-user-a", "memory-user-b"],
      }),
    );
  });

  it("does not merge single-memory entities into an exact text match from another compound scope", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = makeEntityStore({
      listMatches: [
        crossScopeEntity({
          user_id: "user-b",
          agent_id: "agent-a",
          run_id: "run-b",
        }),
      ],
      searchMatches: [],
    });
    m._entityStore = mockEntityStore;

    await m._linkEntitiesForMemory("memory-user-b", "OpenClaw enabled", {
      user_id: "user-b",
      agent_id: "agent-b",
      run_id: "run-b",
    });

    expect(mockEntityStore.update).not.toHaveBeenCalled();
    expect(mockEntityStore.insert).toHaveBeenCalledTimes(1);
    expect(mockEntityStore.insert.mock.calls[0][2][0]).toMatchObject({
      data: "OpenClaw",
      entityType: "ORG",
      user_id: "user-b",
      agent_id: "agent-b",
      run_id: "run-b",
      linkedMemoryIds: ["memory-user-b"],
    });
  });

  it("uses an in-scope exact text match when an out-of-scope exact row appears first", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = makeEntityStore({
      listMatches: [
        crossScopeEntity({
          user_id: "user-a",
          linkedMemoryIds: ["memory-user-a"],
        }),
        {
          ...crossScopeEntity({
            user_id: "user-b",
            linkedMemoryIds: ["memory-user-c"],
          }),
          id: "entity-user-b",
        },
      ],
      searchMatches: [],
    });
    m._entityStore = mockEntityStore;

    await m._linkEntitiesForMemory("memory-user-b", "OpenClaw enabled", {
      user_id: "user-b",
    });

    expect(mockEntityStore.search).not.toHaveBeenCalled();
    expect(mockEntityStore.insert).not.toHaveBeenCalled();
    expect(mockEntityStore.update).toHaveBeenCalledWith(
      "entity-user-b",
      expect.any(Array),
      expect.objectContaining({
        user_id: "user-b",
        linkedMemoryIds: ["memory-user-b", "memory-user-c"],
      }),
    );
  });

  it("does not merge batched add entities into a returned candidate from another user scope", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = makeEntityStore();
    m._entityStore = mockEntityStore;

    const result = await memory.add("OpenClaw is enabled", {
      userId: "user-b",
    });

    expect(mockEntityStore.search).toHaveBeenCalledWith(expect.any(Array), 10, {
      user_id: "user-b",
    });
    expect(result.results).toHaveLength(1);
    expect(mockEntityStore.update).not.toHaveBeenCalled();
    expect(mockEntityStore.insert).toHaveBeenCalledTimes(1);
    expect(mockEntityStore.insert.mock.calls[0][2][0]).toMatchObject({
      data: "OpenClaw",
      entityType: "ORG",
      user_id: "user-b",
      linkedMemoryIds: [result.results[0].id],
    });
  });

  it("uses the first in-scope semantic match during batched add when an out-of-scope candidate ranks first", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = makeEntityStore({
      searchMatches: [
        crossScopeEntity({
          user_id: "user-a",
          linkedMemoryIds: ["memory-user-a"],
        }),
        {
          ...crossScopeEntity({
            user_id: "user-b",
            linkedMemoryIds: ["memory-user-c"],
          }),
          id: "entity-user-b",
          score: 0.97,
        },
      ],
    });
    m._entityStore = mockEntityStore;

    const result = await memory.add("OpenClaw is enabled", {
      userId: "user-b",
    });

    expect(mockEntityStore.search).toHaveBeenCalledWith(expect.any(Array), 10, {
      user_id: "user-b",
    });
    expect(result.results).toHaveLength(1);
    expect(mockEntityStore.insert).not.toHaveBeenCalled();
    expect(mockEntityStore.update).toHaveBeenCalledTimes(1);
    const updatePayload = mockEntityStore.update.mock.calls[0][2];
    expect(mockEntityStore.update.mock.calls[0][0]).toBe("entity-user-b");
    expect(updatePayload).toMatchObject({
      user_id: "user-b",
    });
    expect(updatePayload.linkedMemoryIds).toEqual(
      expect.arrayContaining(["memory-user-c", result.results[0].id]),
    );
    expect(updatePayload.linkedMemoryIds).toHaveLength(2);
  });

  it("uses an in-scope semantic match beyond the first five polluted batched add candidates", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const pollutedMatches = Array.from({ length: 6 }, (_, index) => ({
      ...crossScopeEntity({
        user_id: `user-a-${index}`,
        linkedMemoryIds: [`memory-user-a-${index}`],
      }),
      id: `entity-user-a-${index}`,
      score: 0.99 - index * 0.001,
    }));
    const mockEntityStore = makeEntityStore({
      searchMatches: [
        ...pollutedMatches,
        {
          ...crossScopeEntity({
            user_id: "user-b",
            linkedMemoryIds: ["memory-user-c"],
          }),
          id: "entity-user-b",
          score: 0.96,
        },
      ],
    });
    m._entityStore = mockEntityStore;

    const result = await memory.add("OpenClaw is enabled", {
      userId: "user-b",
    });

    expect(mockEntityStore.search).toHaveBeenCalledWith(expect.any(Array), 10, {
      user_id: "user-b",
    });
    expect(result.results).toHaveLength(1);
    expect(mockEntityStore.insert).not.toHaveBeenCalled();
    expect(mockEntityStore.update.mock.calls[0][0]).toBe("entity-user-b");
    const updatePayload = mockEntityStore.update.mock.calls[0][2];
    expect(updatePayload).toMatchObject({
      user_id: "user-b",
    });
    expect(updatePayload.linkedMemoryIds).toEqual(
      expect.arrayContaining(["memory-user-c", result.results[0].id]),
    );
    expect(updatePayload.linkedMemoryIds).toHaveLength(2);
  });

  it("does not merge batched add entities into an exact text match from another compound scope", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = makeEntityStore({
      listMatches: [
        crossScopeEntity({
          user_id: "user-b",
          agent_id: "agent-a",
          run_id: "run-b",
        }),
      ],
      searchMatches: [],
    });
    m._entityStore = mockEntityStore;

    const result = await memory.add("OpenClaw is enabled", {
      userId: "user-b",
      agentId: "agent-b",
      runId: "run-b",
    });

    expect(result.results).toHaveLength(1);
    expect(mockEntityStore.update).not.toHaveBeenCalled();
    expect(mockEntityStore.insert).toHaveBeenCalledTimes(1);
    expect(mockEntityStore.insert.mock.calls[0][2][0]).toMatchObject({
      data: "OpenClaw",
      entityType: "ORG",
      user_id: "user-b",
      agent_id: "agent-b",
      run_id: "run-b",
      linkedMemoryIds: [result.results[0].id],
    });
  });

  it("continues to merge batched add entities into an in-scope exact text match", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = makeEntityStore({
      listMatches: [
        crossScopeEntity({
          user_id: "user-b",
          agent_id: "agent-b",
          run_id: "run-b",
          linkedMemoryIds: ["memory-user-a"],
        }),
      ],
      searchMatches: [],
    });
    m._entityStore = mockEntityStore;

    const result = await memory.add("OpenClaw is enabled", {
      userId: "user-b",
      agentId: "agent-b",
      runId: "run-b",
    });

    expect(result.results).toHaveLength(1);
    expect(mockEntityStore.insert).not.toHaveBeenCalled();
    expect(mockEntityStore.update).toHaveBeenCalledTimes(1);
    const updatePayload = mockEntityStore.update.mock.calls[0][2];
    expect(updatePayload).toMatchObject({
      data: "OpenClaw",
      entityType: "ORG",
      user_id: "user-b",
      agent_id: "agent-b",
      run_id: "run-b",
    });
    expect(updatePayload.linkedMemoryIds).toEqual(
      expect.arrayContaining(["memory-user-a", result.results[0].id]),
    );
    expect(updatePayload.linkedMemoryIds).toHaveLength(2);
  });

  it("does not use out-of-scope entity matches for search-time entity boosts", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = makeEntityStore({
      searchMatches: [
        crossScopeEntity({
          user_id: "user-a",
          linkedMemoryIds: ["boosted-memory"],
        }),
      ],
    });
    m._entityStore = mockEntityStore;
    m.vectorStore.search = jest.fn().mockResolvedValue([
      {
        id: "plain-memory",
        score: 0.6,
        payload: { data: "plain OpenClaw memory", user_id: "user-b" },
      },
      {
        id: "boosted-memory",
        score: 0.4,
        payload: { data: "lower-score OpenClaw memory", user_id: "user-b" },
      },
    ]);
    m.vectorStore.keywordSearch = jest.fn().mockResolvedValue(null);

    const result = await memory.search("OpenClaw", {
      filters: { user_id: "user-b" },
      topK: 2,
      explain: true,
    });

    expect(result.results.map((item) => item.id)).toEqual([
      "plain-memory",
      "boosted-memory",
    ]);
    expect(result.results[1].score_details?.entityBoost).toBe(0);
  });

  it("continues to use in-scope entity matches for search-time entity boosts", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = makeEntityStore({
      searchMatches: [
        crossScopeEntity({
          user_id: "user-b",
          linkedMemoryIds: ["boosted-memory"],
        }),
      ],
    });
    m._entityStore = mockEntityStore;
    m.vectorStore.search = jest.fn().mockResolvedValue([
      {
        id: "plain-memory",
        score: 0.6,
        payload: { data: "plain OpenClaw memory", user_id: "user-b" },
      },
      {
        id: "boosted-memory",
        score: 0.59,
        payload: { data: "lower-score OpenClaw memory", user_id: "user-b" },
      },
    ]);
    m.vectorStore.keywordSearch = jest.fn().mockResolvedValue(null);

    const result = await memory.search("OpenClaw", {
      filters: { user_id: "user-b" },
      topK: 2,
      explain: true,
    });

    expect(mockEntityStore.search).toHaveBeenCalledWith(
      expect.any(Array),
      500,
      {
        user_id: "user-b",
      },
    );
    expect(result.results.map((item) => item.id)).toEqual([
      "boosted-memory",
      "plain-memory",
    ]);
    expect(result.results[0].score_details?.entityBoost).toBeGreaterThan(0);
  });
});
