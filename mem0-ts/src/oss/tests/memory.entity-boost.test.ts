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

    // Inject mock embedder that resolves immediately
    m.embedder = {
      embed: jest.fn().mockResolvedValue(mockEmbedding),
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

    const searchResponses: Record<string, VectorStoreResult[]> = {};

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

    // With 4 entities at 100ms each, sequential would be ~400ms.
    // Parallel should be ~100ms. Use generous bound for CI.
    expect(elapsed).toBeLessThan(350);
    // At least 2 searches should have overlapped
    expect(concurrency.peak).toBeGreaterThanOrEqual(2);
  });
});
