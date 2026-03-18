/// <reference types="jest" />

import { createHash } from "crypto";

// ─────────────────────────────────────────────────────────────────────────
// Qdrant.findByPayload() - filter construction
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

describe("Qdrant.findByPayload()", () => {
  let store: Qdrant;
  let mockClient: any;

  beforeEach(() => {
    mockClient = {
      search: jest.fn().mockResolvedValue([]),
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

  it("builds correct must conditions from filters object", async () => {
    await store.findByPayload({ hash: "abc123", userId: "u1" }, 1);

    expect(mockClient.scroll).toHaveBeenCalledWith("test", {
      filter: {
        must: [
          { key: "hash", match: { value: "abc123" } },
          { key: "userId", match: { value: "u1" } },
        ],
      },
      limit: 1,
      with_payload: true,
      with_vectors: false,
    });
  });

  it("returns mapped results from scroll response", async () => {
    mockClient.scroll.mockResolvedValueOnce({
      points: [
        { id: "point-1", payload: { data: "test fact", hash: "abc" } },
      ],
    });

    const results = await store.findByPayload({ hash: "abc" });

    expect(results).toEqual([
      { id: "point-1", payload: { data: "test fact", hash: "abc" } },
    ]);
  });

  it("returns empty array when no matches", async () => {
    const results = await store.findByPayload({ hash: "nonexistent" });
    expect(results).toEqual([]);
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Memory.createMemory() - hash dedup via add(infer: false)
// ─────────────────────────────────────────────────────────────────────────

describe("Memory.createMemory() - hash dedup", () => {
  let MemoryClass: any;
  let mockVStore: any;
  let mockEmbedder: any;
  let mockHistory: any;

  beforeEach(() => {
    jest.resetModules();

    mockEmbedder = {
      embed: jest.fn().mockResolvedValue([0.1, 0.2, 0.3, 0.4]),
      embedBatch: jest.fn().mockResolvedValue([[0.1, 0.2, 0.3, 0.4]]),
    };
    mockHistory = {
      addHistory: jest.fn().mockResolvedValue(undefined),
      getHistory: jest.fn().mockResolvedValue([]),
      reset: jest.fn().mockResolvedValue(undefined),
    };
    mockVStore = {
      insert: jest.fn().mockResolvedValue(undefined),
      search: jest.fn().mockResolvedValue([]),
      get: jest.fn().mockResolvedValue(null),
      update: jest.fn().mockResolvedValue(undefined),
      delete: jest.fn().mockResolvedValue(undefined),
      deleteCol: jest.fn().mockResolvedValue(undefined),
      list: jest.fn().mockResolvedValue([[], 0]),
      getUserId: jest.fn().mockResolvedValue("test-user-id"),
      setUserId: jest.fn().mockResolvedValue(undefined),
      initialize: jest.fn().mockResolvedValue(undefined),
      findByPayload: jest.fn().mockResolvedValue([]),
    };

    jest.doMock("../src/utils/factory", () => ({
      EmbedderFactory: { create: jest.fn().mockReturnValue(mockEmbedder) },
      VectorStoreFactory: { create: jest.fn().mockReturnValue(mockVStore) },
      LLMFactory: {
        create: jest.fn().mockReturnValue({
          generateResponse: jest.fn().mockResolvedValue('{"facts":[]}'),
        }),
      },
      HistoryManagerFactory: { create: jest.fn().mockReturnValue(mockHistory) },
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

  function createMemory() {
    return new MemoryClass({
      embedder: { provider: "openai", config: { apiKey: "test-key" } },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test", dimension: 4 },
      },
      llm: { provider: "openai", config: { apiKey: "test-key" } },
      disableHistory: true,
    });
  }

  it("skips insert and returns existing ID when hash match found", async () => {
    const factText = "User prefers dark mode";
    const expectedHash = createHash("md5").update(factText).digest("hex");

    mockVStore.findByPayload.mockResolvedValueOnce([
      { id: "existing-id", payload: { data: factText, hash: expectedHash } },
    ]);

    const mem = createMemory();
    const result = await mem.add(factText, { userId: "u1", infer: false });

    // findByPayload was called with the hash and userId
    expect(mockVStore.findByPayload).toHaveBeenCalledWith(
      expect.objectContaining({ hash: expectedHash, userId: "u1" }),
      1,
    );

    // insert was NOT called (dedup kicked in)
    expect(mockVStore.insert).not.toHaveBeenCalled();

    // returned the existing ID
    expect(result.results[0].id).toBe("existing-id");
  });

  it("proceeds with insert when no hash match found", async () => {
    mockVStore.findByPayload.mockResolvedValueOnce([]);

    const mem = createMemory();
    await mem.add("Brand new fact", { userId: "u1", infer: false });

    // findByPayload was called
    expect(mockVStore.findByPayload).toHaveBeenCalled();

    // insert was called (no dedup match)
    expect(mockVStore.insert).toHaveBeenCalled();
  });

  it("proceeds with insert when findByPayload throws (fail-open)", async () => {
    mockVStore.findByPayload.mockRejectedValueOnce(
      new Error("Qdrant connection failed"),
    );

    const mem = createMemory();
    await mem.add("Some fact", { userId: "u1", infer: false });

    // findByPayload was called and threw
    expect(mockVStore.findByPayload).toHaveBeenCalled();

    // insert was still called (fail-open)
    expect(mockVStore.insert).toHaveBeenCalled();
  });
});
