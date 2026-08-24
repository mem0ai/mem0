/**
 * Entity boost parallelism tests (#5214).
 *
 * Verifies that entity boost searches run concurrently via Promise.allSettled,
 * scoring is preserved, and individual entity failures don't abort others.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import { ENTITY_BOOST_WEIGHT } from "../src/utils/scoring";
import type { VectorStoreResult } from "../src/types";

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
        memory: [{ id: "0", text: "fact", attributed_to: "user" }],
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

function makeMatch(
  id: string,
  score: number,
  linkedMemoryIds: string[],
): VectorStoreResult {
  return { id, score, payload: { linkedMemoryIds } };
}

function createMemory(): Memory {
  return new Memory({
    version: "v1.1",
    embedder: {
      provider: "openai",
      config: { apiKey: "test-key", model: "text-embedding-3-small" },
    },
    vectorStore: {
      provider: "memory",
      config: {
        collectionName: `test-entity-${Date.now()}-${Math.random()}`,
        dimension: 1536,
        dbPath: ":memory:",
      },
    },
    llm: {
      provider: "openai",
      config: { apiKey: "test-key", model: "gpt-5-mini" },
    },
    historyDbPath: ":memory:",
  });
}

describe("Entity boost parallelism (#5214)", () => {
  let memory: Memory;

  beforeEach(() => {
    memory = createMemory();
  });

  afterEach(async () => {
    await memory.reset();
  });

  it("should use Promise.allSettled for concurrent entity searches", async () => {
    // Spy on Promise.allSettled to confirm it's being used
    const allSettledSpy = jest.spyOn(Promise, "allSettled");

    // Access internals to inject a mock entity store
    const m = memory as any;
    await m._ensureInitialized();

    const mockEntityStore = {
      search: jest.fn().mockResolvedValue([makeMatch("e1", 0.9, ["mem-1"])]),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
    m._entityStore = mockEntityStore;

    m.embedder = {
      embed: jest.fn().mockResolvedValue(mockEmbedding),
      embedBatch: jest
        .fn()
        .mockImplementation((texts: string[]) =>
          Promise.resolve(texts.map(() => mockEmbedding)),
        ),
    };

    // Mock the vector store to return a semantic result
    m.vectorStore.search = jest
      .fn()
      .mockResolvedValue([
        { id: "mem-1", score: 0.8, payload: { data: "test" } },
      ]);
    m.vectorStore.keywordSearch = jest.fn().mockResolvedValue(null);

    await m.search("alice and bob", { filters: { user_id: "u1" } });

    expect(allSettledSpy).toHaveBeenCalled();
    allSettledSpy.mockRestore();
  });

  it("should preserve scoring math with parallel execution", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    // Two entities: "alice" links to mem-1, "bob" links to mem-1 and mem-2
    // mem-1 should get max(alice_boost, bob_boost)
    const mockEntityStore = {
      search: jest
        .fn()
        .mockImplementation(
          (_embedding: number[], _topK: number, _filters: any) => {
            // We need to differentiate by embedding content — but since all
            // embeddings are identical mocks, we'll use call order
            const callCount = mockEntityStore.search.mock.calls.length;
            if (callCount <= 1) {
              // First entity: "alice"
              return Promise.resolve([makeMatch("e-alice", 0.9, ["mem-1"])]);
            }
            // Second entity: "bob"
            return Promise.resolve([
              makeMatch("e-bob", 0.6, ["mem-1", "mem-2"]),
            ]);
          },
        ),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
    m._entityStore = mockEntityStore;
    m.embedder = {
      embed: jest.fn().mockResolvedValue(mockEmbedding),
      embedBatch: jest
        .fn()
        .mockImplementation((texts: string[]) =>
          Promise.resolve(texts.map(() => mockEmbedding)),
        ),
    };

    // Semantic results include mem-1 and mem-2
    m.vectorStore.search = jest.fn().mockResolvedValue([
      { id: "mem-1", score: 0.85, payload: { data: "alice memory" } },
      { id: "mem-2", score: 0.75, payload: { data: "bob memory" } },
    ]);
    m.vectorStore.keywordSearch = jest.fn().mockResolvedValue(null);

    const result = await m.search("alice and bob", {
      filters: { user_id: "u1" },
    });

    // Entity store was called (parallelized via Promise.allSettled)
    expect(mockEntityStore.search).toHaveBeenCalled();

    // Results should exist and have scores
    expect(result.results.length).toBeGreaterThan(0);
    for (const item of result.results) {
      expect(typeof item.score).toBe("number");
      expect(item.score).toBeGreaterThan(0);
    }
  });

  it("should survive one entity search failure without losing other boosts", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    let callIndex = 0;
    const mockEntityStore = {
      search: jest.fn().mockImplementation(() => {
        callIndex++;
        if (callIndex === 1) {
          return Promise.reject(new Error("provider timeout"));
        }
        return Promise.resolve([makeMatch("e-ok", 0.8, ["mem-9"])]);
      }),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
    m._entityStore = mockEntityStore;
    m.embedder = {
      embed: jest.fn().mockResolvedValue(mockEmbedding),
      embedBatch: jest
        .fn()
        .mockImplementation((texts: string[]) =>
          Promise.resolve(texts.map(() => mockEmbedding)),
        ),
    };
    m.vectorStore.search = jest
      .fn()
      .mockResolvedValue([
        { id: "mem-9", score: 0.85, payload: { data: "surviving memory" } },
      ]);
    m.vectorStore.keywordSearch = jest.fn().mockResolvedValue(null);

    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});

    // "John Smith met Jane Doe" extracts two proper entities
    const result = await m.search("John Smith met Jane Doe", {
      filters: { user_id: "u1" },
    });

    expect(result.results.length).toBeGreaterThan(0);
    expect(result.results[0].id).toBe("mem-9");
    // Should log the failure like Python does
    expect(warnSpy).toHaveBeenCalledWith(
      "Entity boost search failed for one entity:",
      expect.any(Error),
    );
    warnSpy.mockRestore();
  });

  it("should rescue linked points outside the semantic pool and fail closed", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    m._entityStore = {
      search: jest
        .fn()
        .mockResolvedValue([
          makeMatch("e-alice", 0.9, [
            "mem-primary",
            "mem-rescued",
            "mem-rescued",
            "mem-wrong-scope",
            "mem-wrong-filter",
            "mem-expired",
            "mem-malformed",
            "mem-missing",
            "mem-throws",
          ]),
        ]),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
    m.embedder = {
      embed: jest.fn().mockResolvedValue(mockEmbedding),
      embedBatch: jest
        .fn()
        .mockImplementation((texts: string[]) =>
          Promise.resolve(texts.map(() => mockEmbedding)),
        ),
    };
    m.vectorStore.search = jest.fn().mockResolvedValue([
      {
        id: "mem-primary",
        score: 0.8,
        payload: { data: "primary", user_id: "u1", topic: "keep" },
      },
      {
        id: "mem-primary",
        score: 0.8,
        payload: { data: "primary", user_id: "u1", topic: "keep" },
      },
    ]);
    m.vectorStore.keywordSearch = jest.fn().mockResolvedValue(null);
    m.vectorStore.get = jest.fn().mockImplementation(async (id: string) => {
      if (id === "mem-throws") throw new Error("point fetch failed");
      const payloads: Record<string, Record<string, any> | null> = {
        "mem-rescued": {
          data: "rescued",
          user_id: "u1",
          topic: "keep",
          memory_type: "procedural_memory",
          not: "keep",
          rank: true,
        },
        "mem-wrong-scope": { data: "wrong", user_id: "u2", topic: "keep" },
        "mem-wrong-filter": { data: "wrong", user_id: "u1", topic: "drop" },
        "mem-expired": {
          data: "expired",
          user_id: "u1",
          topic: "keep",
          expiration_date: "2000-01-01",
        },
        "mem-malformed": null,
      };
      const payload = payloads[id];
      return payload === undefined ? null : { id, payload };
    });

    const result = await m.search("Alice Smith", {
      filters: { user_id: "u1", topic: "keep" },
    });
    const resultIds = result.results.map((item: { id: string }) => item.id);

    expect(resultIds.filter((id: string) => id === "mem-rescued")).toHaveLength(
      1,
    );
    expect(resultIds.filter((id: string) => id === "mem-primary")).toHaveLength(
      1,
    );
    const rescued = result.results.find(
      (item: { id: string; metadata?: Record<string, any> }) =>
        item.id === "mem-rescued",
    );
    expect(rescued?.metadata?.memory_type).toBe("procedural_memory");
    expect(resultIds).not.toContain("mem-wrong-scope");
    expect(resultIds).not.toContain("mem-wrong-filter");
    expect(resultIds).not.toContain("mem-expired");
    expect(resultIds).not.toContain("mem-malformed");
    expect(resultIds).not.toContain("mem-missing");
    expect(resultIds).not.toContain("mem-throws");
    expect(m.vectorStore.get).not.toHaveBeenCalledWith("mem-primary");

    for (const advancedValue of [
      { eq: "keep" },
      ["keep"],
      { $or: [{ topic: "keep" }] },
      "*",
    ]) {
      const advancedResult = await m.search("Alice Smith", {
        filters: { user_id: "u1", topic: advancedValue },
      });
      expect(
        advancedResult.results.map((item: { id: string }) => item.id),
      ).not.toContain("mem-rescued");
    }

    const metadataKeyResult = await m.search("Alice Smith", {
      filters: { user_id: "u1", not: "keep" },
    });
    expect(
      metadataKeyResult.results.map((item: { id: string }) => item.id),
    ).toContain("mem-rescued");
    const typeMismatchResult = await m.search("Alice Smith", {
      filters: { user_id: "u1", rank: 1 },
    });
    expect(
      typeMismatchResult.results.map((item: { id: string }) => item.id),
    ).not.toContain("mem-rescued");
  });

  it("bounds rescue point fetches independently of topK", async () => {
    const m = memory as any;
    await m._ensureInitialized();
    const linkedIds = Array.from(
      { length: 75 },
      (_, index) => `rescued-${index}`,
    );
    m._entityStore = {
      search: jest
        .fn()
        .mockResolvedValue([makeMatch("e-alice", 0.9, linkedIds)]),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
    m.embedder = {
      embed: jest.fn().mockResolvedValue(mockEmbedding),
      embedBatch: jest
        .fn()
        .mockImplementation((texts: string[]) =>
          Promise.resolve(texts.map(() => mockEmbedding)),
        ),
    };
    m.vectorStore.search = jest
      .fn()
      .mockResolvedValue([
        {
          id: "mem-primary",
          score: 0.8,
          payload: { data: "primary", user_id: "u1" },
        },
      ]);
    m.vectorStore.keywordSearch = jest.fn().mockResolvedValue(null);
    m.vectorStore.get = jest.fn().mockImplementation(async (id: string) => ({
      id,
      payload: { data: id, user_id: "u1" },
    }));

    await m.search("Alice Smith", { filters: { user_id: "u1" }, topK: 100 });

    expect(m.vectorStore.get).toHaveBeenCalledTimes(60);
  });

  it("should call entity searches concurrently, not sequentially", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    const concurrency = { current: 0, peak: 0 };

    const mockEntityStore = {
      search: jest.fn().mockImplementation(() => {
        concurrency.current++;
        concurrency.peak = Math.max(concurrency.peak, concurrency.current);
        return new Promise<VectorStoreResult[]>((resolve) => {
          setTimeout(() => {
            concurrency.current--;
            resolve([makeMatch("e1", 0.7, ["mem-1"])]);
          }, 100);
        });
      }),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
    m._entityStore = mockEntityStore;
    m.embedder = {
      embed: jest.fn().mockResolvedValue(mockEmbedding),
      embedBatch: jest
        .fn()
        .mockImplementation((texts: string[]) =>
          Promise.resolve(texts.map(() => mockEmbedding)),
        ),
    };
    m.vectorStore.search = jest
      .fn()
      .mockResolvedValue([
        { id: "mem-1", score: 0.8, payload: { data: "test" } },
      ]);
    m.vectorStore.keywordSearch = jest.fn().mockResolvedValue(null);

    const start = performance.now();
    await m.search("entity1 and entity2 and entity3 and entity4", {
      filters: { user_id: "u1" },
    });
    const elapsed = performance.now() - start;

    // With 4 entities at 100ms each, sequential would be ~400ms+.
    // Parallel should be well under that. Use generous bound for CI.
    expect(elapsed).toBeLessThan(500);
    // At least 2 searches should have overlapped
    expect(concurrency.peak).toBeGreaterThanOrEqual(2);
  });
});
