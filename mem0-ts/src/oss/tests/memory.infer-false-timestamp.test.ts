/**
 * infer:false add() must persist updatedAt on the stored payload, matching the
 * infer:true batch pipeline and updateMemory. Without it, get()/getAll()/search()
 * return updatedAt as undefined for every infer:false memory.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import type { SearchResult } from "../src/types";

jest.setTimeout(30000);

// Keep the optional native providers out of CI.
jest.mock("../src/embeddings/google", () => ({ GoogleEmbedder: jest.fn() }));
jest.mock("../src/llms/google", () => ({ GoogleLLM: jest.fn() }));

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
// infer:false never calls the LLM, but the factory still constructs one.
jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest.fn().mockResolvedValue("{}"),
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
        collectionName: `test-infer-false-${Date.now()}-${Math.random()}`,
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

describe("Memory - infer:false timestamps", () => {
  let memory: Memory;
  const userId = `infer_false_${Date.now()}`;

  beforeAll(() => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("get() returns updatedAt equal to createdAt for an infer:false memory", async () => {
    const addResult: SearchResult = await memory.add("I like tea", {
      userId,
      infer: false,
    });
    const id = addResult.results[0].id;

    const item = await memory.get(id);
    expect(item).not.toBeNull();
    expect(item!.createdAt).toBeDefined();
    expect(item!.updatedAt).toBeDefined();
    expect(item!.updatedAt).toBe(item!.createdAt);
  });

  test("getAll() returns updatedAt for infer:false memories", async () => {
    await memory.add("I like coffee", { userId, infer: false });

    const all = await memory.getAll({ filters: { user_id: userId } });
    expect(all.results.length).toBeGreaterThan(0);
    for (const item of all.results) {
      expect(item.updatedAt).toBeDefined();
      expect(item.createdAt).toBeDefined();
    }
  });
});
