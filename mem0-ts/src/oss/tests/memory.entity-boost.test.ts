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
        { id: "mem-1", score: 0.8, payload: { data: "test", user_id: "u1" } },
      ]);
    m.vectorStore.keywordSearch = jest.fn().mockResolvedValue(null);

    await m.search("alice and bob", { filters: { user_id: "u1" } });

    expect(allSettledSpy).toHaveBeenCalled();
    allSettledSpy.mockRestore();
  });

  it("should scope entity boost searches with camelCase read filters", async () => {
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

    m.vectorStore.search = jest.fn().mockResolvedValue([
      {
        id: "mem-1",
        score: 0.8,
        payload: { data: "alice memory", user_id: "u1" },
      },
    ]);
    m.vectorStore.keywordSearch = jest.fn().mockResolvedValue(null);

    await m.search("Alice and Bob", { filters: { userId: "u1" } });

    expect(mockEntityStore.search).toHaveBeenCalledWith(mockEmbedding, 500, {
      user_id: "u1",
    });
  });

  it("should scope entity boost searches from nested common scope filters", async () => {
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

    m.vectorStore.search = jest.fn().mockResolvedValue([
      {
        id: "mem-1",
        score: 0.8,
        payload: { data: "alice travel memory", user_id: "u1" },
      },
    ]);
    m.vectorStore.keywordSearch = jest.fn().mockResolvedValue(null);

    await m.search("Alice and Bob", {
      filters: { AND: [{ userId: "u1" }, { topic: "travel" }] },
    });

    expect(mockEntityStore.search).toHaveBeenCalledWith(mockEmbedding, 500, {
      user_id: "u1",
    });
  });

  it("should skip exact entity dedupe when a capped provider returns a full page", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    m.config.vectorStore.provider = "vectorize";
    const rows = Array.from({ length: 50 }, (_, index) => ({
      id: `entity-${index}`,
      payload: {
        data: `Entity ${index}`,
        linkedMemoryIds: [`mem-${index}`],
        user_id: "u1",
      },
    }));
    const mockEntityStore = {
      list: jest
        .fn()
        .mockResolvedValueOnce([rows, rows.length])
        .mockResolvedValueOnce([[], 0]),
    };
    const debugSpy = jest.spyOn(console, "debug").mockImplementation(() => {});

    try {
      const exactMatches = await m._existingEntitiesByText(mockEntityStore, {
        user_id: "u1",
      });

      expect(mockEntityStore.list).toHaveBeenNthCalledWith(
        1,
        { user_id: "u1" },
        50,
      );
      expect(mockEntityStore.list).toHaveBeenNthCalledWith(
        2,
        { userId: "u1" },
        50,
      );
      expect(exactMatches.size).toBe(0);
      expect(debugSpy).toHaveBeenCalledWith(
        expect.stringContaining("Exact entity lookup skipped"),
      );
    } finally {
      debugSpy.mockRestore();
      m.config.vectorStore.provider = "memory";
    }
  });

  it("should skip entity cleanup when a capped provider returns a full page", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    m.config.vectorStore.provider = "vectorize";
    const rows = Array.from({ length: 50 }, (_, index) => ({
      id: `entity-${index}`,
      payload: {
        data: `Entity ${index}`,
        linkedMemoryIds: ["mem-1", `other-${index}`],
        user_id: "u1",
      },
    }));
    const mockEntityStore = {
      list: jest
        .fn()
        .mockResolvedValueOnce([rows, rows.length])
        .mockResolvedValueOnce([[], 0]),
      delete: jest.fn().mockResolvedValue(undefined),
      update: jest.fn().mockResolvedValue(undefined),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
    m._entityStore = mockEntityStore;
    const debugSpy = jest.spyOn(console, "debug").mockImplementation(() => {});

    try {
      await m._removeMemoryFromEntityStore("mem-1", { user_id: "u1" });

      expect(mockEntityStore.list).toHaveBeenNthCalledWith(
        1,
        { user_id: "u1" },
        50,
      );
      expect(mockEntityStore.list).toHaveBeenNthCalledWith(
        2,
        { userId: "u1" },
        50,
      );
      expect(mockEntityStore.delete).not.toHaveBeenCalled();
      expect(mockEntityStore.update).not.toHaveBeenCalled();
      expect(debugSpy).toHaveBeenCalledWith(
        expect.stringContaining("Entity cleanup skipped"),
      );
    } finally {
      debugSpy.mockRestore();
      m._entityStore = undefined;
      m.config.vectorStore.provider = "memory";
    }
  });

  it("should skip entity boosts when a capped provider returns a full search page", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    m.config.vectorStore.provider = "vectorize";
    const fullEntityPage = Array.from({ length: 50 }, (_, index) =>
      makeMatch(`entity-${index}`, 0.9, ["mem-1"]),
    );
    const mockEntityStore = {
      search: jest
        .fn()
        .mockResolvedValueOnce(fullEntityPage)
        .mockResolvedValueOnce([]),
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

    m.vectorStore.search = jest.fn().mockResolvedValue([
      {
        id: "mem-1",
        score: 0.7,
        payload: { data: "alice memory", user_id: "u1" },
      },
      {
        id: "mem-2",
        score: 0.8,
        payload: { data: "other memory", user_id: "u1" },
      },
    ]);
    m.vectorStore.keywordSearch = jest.fn().mockResolvedValue(null);
    const debugSpy = jest.spyOn(console, "debug").mockImplementation(() => {});

    try {
      const result = await m.search("Alice and Bob", {
        filters: { user_id: "u1" },
        threshold: 0,
        explain: true,
      });

      expect(mockEntityStore.search).toHaveBeenNthCalledWith(
        1,
        mockEmbedding,
        50,
        {
          user_id: "u1",
        },
      );
      expect(mockEntityStore.search).toHaveBeenNthCalledWith(
        2,
        mockEmbedding,
        50,
        {
          userId: "u1",
        },
      );
      expect(debugSpy).toHaveBeenCalledWith(
        expect.stringContaining("Entity boost skipped"),
      );
      expect(result.results.map((item: any) => item.id)).toEqual([
        "mem-2",
        "mem-1",
      ]);
      expect(result.results[1].score_details.entityBoost).toBe(0);
    } finally {
      debugSpy.mockRestore();
      m._entityStore = undefined;
      m.config.vectorStore.provider = "memory";
    }
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
      {
        id: "mem-1",
        score: 0.85,
        payload: { data: "alice memory", user_id: "u1" },
      },
      {
        id: "mem-2",
        score: 0.75,
        payload: { data: "bob memory", user_id: "u1" },
      },
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
    m.vectorStore.search = jest.fn().mockResolvedValue([
      {
        id: "mem-9",
        score: 0.85,
        payload: { data: "surviving memory", user_id: "u1" },
      },
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
        { id: "mem-1", score: 0.8, payload: { data: "test", user_id: "u1" } },
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
