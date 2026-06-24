/**
 * Phase 7a entity dedup tests — same-name entities with different types must not merge.
 * Related to mem0ai/mem0#5587.
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
    generateResponse: jest.fn().mockResolvedValue(
      JSON.stringify({
        memory: [
          { text: "Python is a language" },
          { text: "Python is a snake" },
        ],
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

jest.mock("../src/utils/entity_extraction", () => ({
  extractEntitiesBatch: jest.fn().mockReturnValue([
    [{ type: "PROPER", text: "Python" }],
    [{ type: "NOUN", text: "Python" }],
  ]),
  extractEntities: jest.fn().mockReturnValue([]),
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
        collectionName: `test-dedup-${Date.now()}-${Math.random()}`,
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

describe("Phase 7a entity type dedup (#5587)", () => {
  let memory: Memory;

  beforeEach(async () => {
    memory = createMemory();
    const m = memory as any;
    await m._ensureInitialized();

    const insert = jest.fn().mockResolvedValue(undefined);
    m._entityStore = {
      search: jest.fn().mockResolvedValue([]),
      insert,
      update: jest.fn().mockResolvedValue(undefined),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
    m._entityStoreInsertSpy = insert;
  });

  afterEach(async () => {
    await memory.reset();
  });

  it("creates separate entity records for same name with different types", async () => {
    const m = memory as any;
    const result = await memory.add("Python language and snake", {
      userId: "u1",
    });

    expect(result.results.length).toBe(2);
    expect(m._entityStoreInsertSpy).toHaveBeenCalledTimes(1);

    const payloads = m._entityStoreInsertSpy.mock.calls[0][2] as Array<
      Record<string, unknown>
    >;
    expect(payloads).toHaveLength(2);
    expect(new Set(payloads.map((p) => p.entityType))).toEqual(
      new Set(["PROPER", "NOUN"]),
    );
    for (const payload of payloads) {
      expect(payload.linkedMemoryIds).toHaveLength(1);
    }
  });
});
