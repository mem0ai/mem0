/**
 * Reranker integration tests for Memory.search().
 *
 * Verifies the per-search `rerank` flag: when a reranker is configured and
 * `rerank: true` is passed, search reorders results by the reranker's output;
 * otherwise results pass through unchanged. Failures degrade gracefully.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import { CohereReranker } from "../src/rerankers/cohere";
import type { RerankResult } from "../src/rerankers/base";

jest.setTimeout(15000);

jest.mock("../src/embeddings/google", () => ({
  GoogleEmbedder: jest.fn(),
}));
jest.mock("../src/llms/google", () => ({
  GoogleLLM: jest.fn(),
}));
jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest
      .fn()
      .mockResolvedValue(JSON.stringify({ memory: [] })),
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

function createMemory(config: Record<string, any> = {}): Memory {
  return new Memory({
    version: "v1.1",
    embedder: {
      provider: "openai",
      config: { apiKey: "test-key", model: "text-embedding-3-small" },
    },
    vectorStore: {
      provider: "memory",
      config: {
        collectionName: `test-rerank-${Date.now()}-${Math.random()}`,
        dimension: 1536,
        dbPath: ":memory:",
      },
    },
    llm: {
      provider: "openai",
      config: { apiKey: "test-key", model: "gpt-5-mini" },
    },
    historyDbPath: ":memory:",
    ...config,
  });
}

// Two semantic results whose natural (score-sorted) order is [alpha, bravo].
async function primeSearch(m: any) {
  await m._ensureInitialized();
  m.embedder = { embed: jest.fn().mockResolvedValue(mockEmbedding) };
  m.vectorStore.search = jest.fn().mockResolvedValue([
    { id: "a", score: 0.9, payload: { data: "alpha" } },
    { id: "b", score: 0.8, payload: { data: "bravo" } },
  ]);
  m.vectorStore.keywordSearch = jest.fn().mockResolvedValue(null);
}

describe("Memory.search reranking", () => {
  it("reorders results by the reranker when rerank:true, adding rerankScore while preserving the original vector score", async () => {
    const memory = createMemory();
    const m = memory as any;
    await primeSearch(m);

    const rerank = jest
      .fn<Promise<RerankResult[]>, [string, string[], number?]>()
      .mockResolvedValue([
        { index: 1, rerankScore: 0.99 }, // bravo
        { index: 0, rerankScore: 0.4 }, // alpha
      ]);
    m.reranker = { rerank };

    const result = await m.search("what did i eat", {
      filters: { user_id: "u1" },
      rerank: true,
    });

    expect(rerank).toHaveBeenCalledWith(
      "what did i eat",
      ["alpha", "bravo"],
      expect.any(Number),
    );
    expect(result.results.map((r: any) => r.memory)).toEqual([
      "bravo",
      "alpha",
    ]);
    expect(result.results[0].rerankScore).toBe(0.99);
    expect(result.results[1].rerankScore).toBe(0.4);
    // The original vector similarity `score` must survive reranking.
    expect(result.results[0].score).toBe(0.8); // bravo's original vector score
    expect(result.results[1].score).toBe(0.9); // alpha's original vector score

    await memory.reset();
  });

  it("leaves results untouched and does not call the reranker when rerank is omitted", async () => {
    const memory = createMemory();
    const m = memory as any;
    await primeSearch(m);
    const rerank = jest.fn();
    m.reranker = { rerank };

    const result = await m.search("what did i eat", {
      filters: { user_id: "u1" },
    });

    expect(rerank).not.toHaveBeenCalled();
    expect(result.results.map((r: any) => r.memory)).toEqual([
      "alpha",
      "bravo",
    ]);
    expect(result.results[0].rerankScore).toBeUndefined();

    await memory.reset();
  });

  it("is a no-op (no throw) when rerank:true but no reranker is configured", async () => {
    const memory = createMemory();
    const m = memory as any;
    await primeSearch(m);

    const result = await m.search("what did i eat", {
      filters: { user_id: "u1" },
      rerank: true,
    });

    expect(result.results.map((r: any) => r.memory)).toEqual([
      "alpha",
      "bravo",
    ]);

    await memory.reset();
  });

  it("falls back to the original results when the reranker throws", async () => {
    const memory = createMemory();
    const m = memory as any;
    await primeSearch(m);
    m.reranker = {
      rerank: jest.fn().mockRejectedValue(new Error("provider down")),
    };
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});

    const result = await m.search("what did i eat", {
      filters: { user_id: "u1" },
      rerank: true,
    });

    expect(result.results.map((r: any) => r.memory)).toEqual([
      "alpha",
      "bravo",
    ]);
    expect(warnSpy).toHaveBeenCalled();

    warnSpy.mockRestore();
    await memory.reset();
  });

  it("wires a reranker from config in the constructor", () => {
    const memory = createMemory({
      reranker: { provider: "cohere", config: { apiKey: "test-key" } },
    });

    expect((memory as any).reranker).toBeInstanceOf(CohereReranker);
  });
});
