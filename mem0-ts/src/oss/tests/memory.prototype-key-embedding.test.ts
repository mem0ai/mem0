/// <reference types="jest" />
/** add() with infer=false must embed Object.prototype-colliding text instead of resolving it off the prototype chain. */
import { Memory } from "../src/memory";
import { MemoryVectorStore } from "../src/vector_stores/memory";
import type { SearchResult } from "../src/types";

const mockEmbedding = new Array(1536).fill(0.1);
const mockEmbed = jest.fn().mockResolvedValue(mockEmbedding);

jest.mock("../src/embeddings/openai", () => ({
  OpenAIEmbedder: jest.fn().mockImplementation(() => ({
    embed: mockEmbed,
    embedBatch: jest.fn(),
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
        collectionName: `test-proto-${Date.now()}-${Math.random()}`,
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

describe("add() with infer=false and Object.prototype-colliding text", () => {
  let memory: Memory;
  let insertSpy: jest.SpyInstance;

  beforeEach(() => {
    memory = createMemory();
    mockEmbed.mockClear();
    insertSpy = jest.spyOn(MemoryVectorStore.prototype, "insert");
  });

  afterEach(async () => {
    insertSpy.mockRestore();
    await memory.reset();
  });

  test.each([
    "constructor",
    "toString",
    "valueOf",
    "hasOwnProperty",
    "__proto__",
  ])(
    'embeds "%s" instead of resolving it off Object.prototype',
    async (text) => {
      const result: SearchResult = await memory.add(text, {
        userId: "u1",
        infer: false,
      });

      expect(mockEmbed).toHaveBeenCalledWith(text, "add");

      const [storedVectors] =
        insertSpy.mock.calls[insertSpy.mock.calls.length - 1];
      expect(Array.isArray(storedVectors[0])).toBe(true);
      expect(storedVectors[0]).toEqual(mockEmbedding);
      expect(
        storedVectors[0].every((n: unknown) => typeof n === "number"),
      ).toBe(true);

      expect(result.results[0].memory).toBe(text);
    },
  );
});

describe("update() metadata-only on Object.prototype-colliding text (#6323)", () => {
  let memory: Memory;
  let updateSpy: jest.SpyInstance;

  beforeEach(() => {
    memory = createMemory();
    updateSpy = jest.spyOn(MemoryVectorStore.prototype, "update");
  });

  afterEach(async () => {
    updateSpy.mockRestore();
    await memory.reset();
  });

  test.each([
    "constructor",
    "toString",
    "valueOf",
    "hasOwnProperty",
    "__proto__",
  ])(
    're-embeds "%s" on a metadata-only update instead of resolving it off Object.prototype',
    async (text) => {
      const added: SearchResult = await memory.add(text, {
        userId: "u1",
        infer: false,
      });
      const memoryId = added.results[0].id!;
      mockEmbed.mockClear();

      await memory.update(memoryId, { metadata: { pinned: true } });

      expect(mockEmbed).toHaveBeenCalledWith(text, "update");

      const [, storedVector] =
        updateSpy.mock.calls[updateSpy.mock.calls.length - 1];
      expect(Array.isArray(storedVector)).toBe(true);
      expect(storedVector).toEqual(mockEmbedding);
    },
  );
});
