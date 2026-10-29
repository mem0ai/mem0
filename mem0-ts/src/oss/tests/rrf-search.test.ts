import { Memory } from "../src/memory";

const mockEmbedder = {
  embed: jest.fn().mockResolvedValue(new Array(768).fill(0.1)),
  embedBatch: jest.fn().mockResolvedValue([]),
};
const mockVStore: any = {
  search: jest.fn(),
  initialize: jest.fn().mockResolvedValue(undefined),
  getUserId: jest.fn().mockResolvedValue("test-user-id"),
  setUserId: jest.fn().mockResolvedValue(undefined),
};

jest.mock("../src/utils/factory", () => ({
  EmbedderFactory: { create: () => mockEmbedder },
  VectorStoreFactory: { create: () => mockVStore },
  LLMFactory: { create: () => ({ generateResponse: jest.fn() }) },
}));
jest.mock("../src/utils/telemetry", () => ({
  captureClientEvent: jest.fn().mockResolvedValue(undefined),
  isTelemetryEnabled: jest.fn(() => false),
}));

describe("RRF search integration", () => {
  it("propagates RRF config through Memory.search scoring", async () => {
    mockVStore.search.mockResolvedValueOnce([
      {
        id: "mem-1",
        payload: { data: "first memory", user_id: "u1" },
        score: 0.95,
      },
      {
        id: "mem-2",
        payload: { data: "second memory", user_id: "u1" },
        score: 0.8,
      },
    ]);

    const mem = new Memory({
      embedder: {
        provider: "lmstudio",
        config: {
          model: "nomic-embed-text-v1.5",
          baseURL: "http://localhost:1234/v1",
          embeddingDims: 768,
        },
      },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test-rrf", dimension: 768 },
      },
      llm: {
        provider: "lmstudio",
        config: { baseURL: "http://localhost:1234/v1" },
      },
      disableHistory: true,
      fusionStrategy: "rrf",
      rrfK: 7,
    });

    const result = await mem.search("query", {
      filters: { user_id: "u1" },
      explain: true,
    });

    expect(result.results[0]).toHaveProperty("score_details");
    expect((result.results[0] as any).score_details).toMatchObject({
      fusionStrategy: "rrf",
      rrfK: 7,
      maxPossibleScore: 1 / 8,
    });
    expect(result.results.map((item: any) => item.id)).toEqual([
      "mem-1",
      "mem-2",
    ]);
    expect(result.results[0].score).toBeCloseTo(1 / 8);
    expect(result.results[1].score).toBeCloseTo(1 / 9);
    expect(mockEmbedder.embed).toHaveBeenCalledTimes(1);
    expect(mockVStore.search).toHaveBeenCalledTimes(1);
    expect(mockVStore.search).toHaveBeenCalledWith(
      new Array(768).fill(0.1),
      80,
      { user_id: "u1" },
    );
  });

  it("fuses keyword-only and entity-only scoped payloads into the union", async () => {
    mockEmbedder.embed.mockClear();
    mockEmbedder.embedBatch.mockResolvedValue([new Array(768).fill(0.1)]);
    mockVStore.search.mockReset();
    mockVStore.search.mockResolvedValue([
      {
        id: "semantic",
        payload: { data: "semantic memory", user_id: "u1" },
        score: 0.95,
      },
      {
        id: "below-threshold",
        payload: { data: "below threshold", user_id: "u1" },
        score: 0.05,
      },
    ]);
    mockVStore.keywordSearch = jest.fn().mockResolvedValue([
      {
        id: "keyword-only",
        payload: { data: "keyword memory", user_id: "u1" },
        score: 100,
      },
    ]);
    mockVStore.getByIds = jest.fn().mockResolvedValue([
      {
        id: "entity-only",
        payload: { data: "entity memory", user_id: "u1" },
      },
    ]);

    const mem = new Memory({
      embedder: {
        provider: "lmstudio",
        config: {
          model: "nomic-embed-text-v1.5",
          baseURL: "http://localhost:1234/v1",
          embeddingDims: 768,
        },
      },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test-rrf-union", dimension: 768 },
      },
      llm: {
        provider: "lmstudio",
        config: { baseURL: "http://localhost:1234/v1" },
      },
      disableHistory: true,
      fusionStrategy: "rrf",
      rrfK: 1,
    });
    const internals = mem as any;
    await internals._ensureInitialized();
    internals._entityStore = {
      initialize: jest.fn().mockResolvedValue(undefined),
      search: jest.fn().mockResolvedValue([
        {
          id: "entity-record",
          score: 0.9,
          payload: { linkedMemoryIds: ["entity-only", "semantic"] },
        },
      ]),
    };

    const result = await mem.search("John Smith", {
      filters: { user_id: "u1" },
      threshold: 0.1,
      explain: true,
    });

    expect(result.results.map((item) => item.id)).toEqual(
      expect.arrayContaining(["semantic", "keyword-only", "entity-only"]),
    );
    expect(result.results).not.toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "below-threshold" }),
      ]),
    );
    expect(
      (result.results.find((item) => item.id === "keyword-only") as any)
        ?.score_details?.bm25Score,
    ).toBe(100);
    expect(mockVStore.getByIds).toHaveBeenCalledTimes(1);
    expect(mockVStore.getByIds).toHaveBeenCalledWith(["entity-only"], {
      user_id: "u1",
    });
    expect(internals._entityStore.search).toHaveBeenCalledWith(
      expect.any(Array),
      500,
      { user_id: "u1" },
    );
  });

  it("warns and skips entity-only expansion when scoped batches are unsupported", async () => {
    mockEmbedder.embedBatch.mockResolvedValue([new Array(768).fill(0.1)]);
    mockVStore.search.mockReset();
    mockVStore.search.mockResolvedValue([
      {
        id: "semantic",
        payload: { data: "semantic memory", user_id: "u1" },
        score: 0.95,
      },
    ]);
    mockVStore.keywordSearch = jest.fn().mockResolvedValue(null);
    mockVStore.getByIds = undefined;

    const mem = new Memory({
      embedder: {
        provider: "lmstudio",
        config: {
          model: "nomic-embed-text-v1.5",
          baseURL: "http://localhost:1234/v1",
          embeddingDims: 768,
        },
      },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test-rrf-unsupported", dimension: 768 },
      },
      llm: {
        provider: "lmstudio",
        config: { baseURL: "http://localhost:1234/v1" },
      },
      disableHistory: true,
      fusionStrategy: "rrf",
      rrfK: 1,
    });
    const internals = mem as any;
    await internals._ensureInitialized();
    internals._entityStore = {
      initialize: jest.fn().mockResolvedValue(undefined),
      search: jest.fn().mockResolvedValue([
        {
          id: "entity-record",
          score: 0.9,
          payload: { linkedMemoryIds: ["entity-only"] },
        },
      ]),
    };
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});

    const result = await mem.search("John Smith", {
      filters: { user_id: "u1" },
    });

    expect(result.results.map((item) => item.id)).toEqual(["semantic"]);
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("scoped batch hydration"),
    );
    warnSpy.mockRestore();
  });

  it("retains source ranks when expired semantic and keyword payloads are removed", async () => {
    mockEmbedder.embedBatch.mockResolvedValue([]);
    mockVStore.search.mockReset();
    mockVStore.search.mockResolvedValue([
      {
        id: "expired-semantic",
        payload: {
          data: "expired semantic",
          expiration_date: "2000-01-01",
          user_id: "u1",
        },
        score: 0.99,
      },
      {
        id: "visible-semantic",
        payload: { data: "visible semantic", user_id: "u1" },
        score: 0.8,
      },
    ]);
    mockVStore.keywordSearch = jest.fn().mockResolvedValue([
      {
        id: "expired-keyword",
        payload: {
          data: "expired keyword",
          expiration_date: "2000-01-01",
          user_id: "u1",
        },
        score: 100,
      },
      {
        id: "visible-keyword",
        payload: { data: "visible keyword", user_id: "u1" },
        score: 10,
      },
    ]);

    const mem = new Memory({
      embedder: {
        provider: "lmstudio",
        config: {
          model: "nomic-embed-text-v1.5",
          baseURL: "http://localhost:1234/v1",
          embeddingDims: 768,
        },
      },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test-rrf-expired-ranks", dimension: 768 },
      },
      llm: {
        provider: "lmstudio",
        config: { baseURL: "http://localhost:1234/v1" },
      },
      disableHistory: true,
      fusionStrategy: "rrf",
      rrfK: 1,
    });

    const result = await mem.search("query", {
      filters: { user_id: "u1" },
      explain: true,
      topK: 2,
    });

    expect(result.results.map((item) => item.id)).toEqual(
      expect.arrayContaining(["visible-semantic", "visible-keyword"]),
    );
    expect(result.results).not.toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "expired-semantic" }),
        expect.objectContaining({ id: "expired-keyword" }),
      ]),
    );
    const semanticDetails = (
      result.results.find((item) => item.id === "visible-semantic") as any
    ).score_details;
    const keywordDetails = (
      result.results.find((item) => item.id === "visible-keyword") as any
    ).score_details;
    expect(semanticDetails.semanticRank).toBe(2);
    expect(keywordDetails.bm25Rank).toBe(2);
  });
});
