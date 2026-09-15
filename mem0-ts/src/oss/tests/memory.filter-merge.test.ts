/**
 * OSS Memory unit tests — advanced metadata filter merging in search().
 *
 * When multiple conditions target the same field (a range expressed with AND,
 * or a top-level operator plus an AND on the same field), the processed filter
 * must combine the operators ({gte:10} + {lte:20} -> {gte:10, lte:20}) instead
 * of the later condition shallow-overwriting the earlier one. This mirrors the
 * Python SDK's Memory._process_metadata_filters.merge_filters.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";

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
    embedBatch: jest.fn().mockResolvedValue([mockEmbedding]),
  })),
}));

describe("Memory - search() metadata filter merge", () => {
  let memory: Memory;

  beforeAll(async () => {
    memory = new Memory({
      version: "v1.1",
      embedder: {
        provider: "openai",
        config: { apiKey: "test-key", model: "text-embedding-3-small" },
      },
      llm: {
        provider: "openai",
        config: { apiKey: "test-key", model: "gpt-5-mini" },
      },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "filter-merge-test" },
      },
    });
    await new Promise((resolve) => setTimeout(resolve, 500));
  });

  afterAll(async () => {
    try {
      await memory.reset();
    } catch (e) {
      // ignore cleanup errors
    }
  });

  it("combines two AND conditions on the same field into one operator dict", async () => {
    const searchSpy = jest
      .spyOn((memory as any).vectorStore, "search")
      .mockResolvedValue([]);

    await memory.search("q", {
      filters: {
        user_id: "u1",
        AND: [{ age: { gte: 10 } }, { age: { lte: 20 } }],
      },
    });

    expect(searchSpy).toHaveBeenCalled();
    const passedFilters = searchSpy.mock.calls[0][2] as Record<string, any>;
    // Both bounds must survive. A shallow overwrite drops the gte bound and
    // the query becomes age <= 20 only (over-inclusive).
    expect(passedFilters.age).toEqual({ gte: 10, lte: 20 });
    expect(passedFilters.user_id).toBe("u1");

    searchSpy.mockRestore();
  });

  it("combines a top-level operator with an AND on the same field", async () => {
    const searchSpy = jest
      .spyOn((memory as any).vectorStore, "search")
      .mockResolvedValue([]);

    await memory.search("q", {
      filters: {
        user_id: "u1",
        age: { gte: 10 },
        AND: [{ age: { lte: 20 } }],
      },
    });

    const passedFilters = searchSpy.mock.calls[0][2] as Record<string, any>;
    expect(passedFilters.age).toEqual({ gte: 10, lte: 20 });

    searchSpy.mockRestore();
  });
});
