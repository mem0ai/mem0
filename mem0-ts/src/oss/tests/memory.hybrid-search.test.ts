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
    embedBatch: jest
      .fn()
      .mockImplementation((texts: string[]) =>
        Promise.resolve(texts.map(() => mockEmbedding)),
      ),
    embeddingDims: 1536,
  })),
}));

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
        collectionName: `test-hybrid-${Date.now()}-${Math.random()}`,
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

describe("Memory.search hybrid candidates", () => {
  it("returns a keyword-only match outside the semantic result pool", async () => {
    const memory = createMemory();
    const internals = memory as any;
    await internals._ensureInitialized();

    internals.vectorStore.search = jest.fn().mockResolvedValue([]);
    internals.vectorStore.keywordSearch = jest.fn().mockResolvedValue([
      {
        id: "keyword-only",
        score: 20,
        payload: { data: "Error code ERR_AUTH_0042", user_id: "test" },
      },
    ]);

    const result = await memory.search("ERR_AUTH_0042", {
      filters: { user_id: "test" },
    });

    expect(result.results.map((item) => item.id)).toEqual(["keyword-only"]);
    expect(result.results[0].memory).toBe("Error code ERR_AUTH_0042");

    await memory.reset();
  });
});
