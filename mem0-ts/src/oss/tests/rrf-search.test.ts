import { Memory } from "../src/memory";

const mockEmbedder = {
  embed: jest.fn().mockResolvedValue(new Array(768).fill(0.1)),
  embedBatch: jest.fn().mockResolvedValue([]),
};
const mockVStore = {
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
});
