/// <reference types="jest" />

// ─────────────────────────────────────────────────────────────────────────
// Qdrant - scoreThreshold forwarding
// ─────────────────────────────────────────────────────────────────────────

jest.mock("@qdrant/js-client-rest", () => ({
  QdrantClient: jest.fn().mockImplementation(() => ({
    search: jest.fn().mockResolvedValue([]),
    createCollection: jest.fn().mockResolvedValue(undefined),
    scroll: jest.fn().mockResolvedValue({ points: [] }),
    getCollection: jest.fn().mockResolvedValue({
      config: { params: { vectors: { size: 4, distance: "Cosine" } } },
    }),
  })),
}));

import { Qdrant } from "../src/vector_stores/qdrant";

describe("Qdrant - scoreThreshold", () => {
  let store: Qdrant;
  let mockClient: any;

  beforeEach(() => {
    mockClient = {
      search: jest.fn().mockResolvedValue([
        { id: "id1", payload: { data: "test" }, score: 0.9 },
      ]),
      createCollection: jest.fn().mockResolvedValue(undefined),
      scroll: jest.fn().mockResolvedValue({ points: [] }),
      getCollection: jest.fn().mockResolvedValue({
        config: { params: { vectors: { size: 4, distance: "Cosine" } } },
      }),
    };

    store = new Qdrant({
      client: mockClient,
      collectionName: "test",
      embeddingModelDims: 4,
      dimension: 4,
    });
  });

  it("passes score_threshold to Qdrant client when scoreThreshold is provided", async () => {
    await store.search([1, 0, 0, 0], 5, undefined, 0.7);

    expect(mockClient.search).toHaveBeenCalledWith(
      "test",
      expect.objectContaining({ score_threshold: 0.7 }),
    );
  });

  it("omits score_threshold when scoreThreshold is not provided", async () => {
    await store.search([1, 0, 0, 0], 5);

    const searchParams = mockClient.search.mock.calls[0][1];
    expect(searchParams).not.toHaveProperty("score_threshold");
  });

  it("omits score_threshold when scoreThreshold is undefined", async () => {
    await store.search([1, 0, 0, 0], 5, undefined, undefined);

    const searchParams = mockClient.search.mock.calls[0][1];
    expect(searchParams).not.toHaveProperty("score_threshold");
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Memory.search() - threshold forwarding
// ─────────────────────────────────────────────────────────────────────────

describe("Memory.search() - threshold forwarding", () => {
  let MemoryClass: any;
  let mockVStore: any;
  let mockEmbedder: any;

  beforeEach(() => {
    jest.resetModules();

    mockEmbedder = {
      embed: jest.fn().mockResolvedValue([0.1, 0.2, 0.3, 0.4]),
      embedBatch: jest.fn().mockResolvedValue([[0.1, 0.2, 0.3, 0.4]]),
    };
    mockVStore = {
      insert: jest.fn().mockResolvedValue(undefined),
      search: jest.fn().mockResolvedValue([
        {
          id: "mem-1",
          payload: {
            data: "User likes hiking",
            userId: "u1",
            hash: "abc",
            createdAt: "2026-01-01",
          },
          score: 0.9,
        },
      ]),
      get: jest.fn().mockResolvedValue(null),
      update: jest.fn().mockResolvedValue(undefined),
      delete: jest.fn().mockResolvedValue(undefined),
      deleteCol: jest.fn().mockResolvedValue(undefined),
      list: jest.fn().mockResolvedValue([[], 0]),
      getUserId: jest.fn().mockResolvedValue("test-user-id"),
      setUserId: jest.fn().mockResolvedValue(undefined),
      initialize: jest.fn().mockResolvedValue(undefined),
    };

    const mockLlm = {
      generateResponse: jest.fn().mockResolvedValue('{"facts":[]}'),
    };

    jest.doMock("../src/utils/factory", () => ({
      EmbedderFactory: { create: jest.fn().mockReturnValue(mockEmbedder) },
      VectorStoreFactory: { create: jest.fn().mockReturnValue(mockVStore) },
      LLMFactory: { create: jest.fn().mockReturnValue(mockLlm) },
      HistoryManagerFactory: {
        create: jest.fn().mockReturnValue({
          addHistory: jest.fn().mockResolvedValue(undefined),
          getHistory: jest.fn().mockResolvedValue([]),
          reset: jest.fn().mockResolvedValue(undefined),
        }),
      },
    }));
    jest.doMock("../src/utils/telemetry", () => ({
      captureClientEvent: jest.fn().mockResolvedValue(undefined),
    }));

    MemoryClass = require("../src/memory").Memory;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("forwards threshold to vectorStore.search() as 4th argument", async () => {
    const mem = new MemoryClass({
      embedder: { provider: "openai", config: { apiKey: "test-key" } },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test", dimension: 4 },
      },
      llm: { provider: "openai", config: { apiKey: "test-key" } },
      disableHistory: true,
    });

    await mem.search("what does the user like", {
      userId: "u1",
      threshold: 0.7,
    });

    expect(mockVStore.search).toHaveBeenCalledWith(
      expect.any(Array),
      expect.any(Number),
      expect.objectContaining({ userId: "u1" }),
      0.7,
    );
  });

  it("passes undefined threshold when not provided", async () => {
    const mem = new MemoryClass({
      embedder: { provider: "openai", config: { apiKey: "test-key" } },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test", dimension: 4 },
      },
      llm: { provider: "openai", config: { apiKey: "test-key" } },
      disableHistory: true,
    });

    await mem.search("what does the user like", { userId: "u1" });

    expect(mockVStore.search).toHaveBeenCalledWith(
      expect.any(Array),
      expect.any(Number),
      expect.objectContaining({ userId: "u1" }),
      undefined,
    );
  });
});
