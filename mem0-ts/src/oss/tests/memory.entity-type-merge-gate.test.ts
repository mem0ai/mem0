/**
 * Entity type merge gate (parity with Python #5497 / issue #6529).
 * Entities with the same text but different entityType must not merge.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";

jest.setTimeout(15000);

jest.mock("../src/embeddings/google", () => ({ GoogleEmbedder: jest.fn() }));
jest.mock("../src/llms/google", () => ({ GoogleLLM: jest.fn() }));
jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest.fn().mockResolvedValue(
      JSON.stringify({ memory: [{ id: "0", text: "Python fact", attributed_to: "user" }] }),
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

// Extracted entity helper is pure enough — stub to control types.
jest.mock("../src/utils/entity_extraction", () => {
  const actual = jest.requireActual("../src/utils/entity_extraction");
  return {
    ...actual,
    extractEntities: jest.fn(),
    extractEntitiesBatch: jest.fn(),
  };
});

import {
  extractEntities,
  extractEntitiesBatch,
} from "../src/utils/entity_extraction";

describe("entity_type merge gate (#6529)", () => {
  test("_entityTypesConflict helper: differ only when both typed and unequal", () => {
    const m = new Memory({
      version: "v1.1",
      embedder: {
        provider: "openai",
        config: { apiKey: "k", model: "text-embedding-3-small" },
      },
      vectorStore: {
        provider: "memory",
        config: {
          collectionName: "et-gate",
          dimension: 1536,
          dbPath: ":memory:",
        },
      },
      llm: { provider: "openai", config: { apiKey: "k", model: "gpt-5-mini" } },
      historyDbPath: ":memory:",
    }) as any;

    expect(m._entityTypesConflict("language", "animal")).toBe(true);
    expect(m._entityTypesConflict("language", "language")).toBe(false);
    expect(m._entityTypesConflict("language", null)).toBe(false);
    expect(m._entityTypesConflict(null, "language")).toBe(false);
    expect(m._entityTypesConflict("", "language")).toBe(false);
  });

  test("_linkEntitiesForMemory inserts instead of merging when types differ", async () => {
    const m = new Memory({
      version: "v1.1",
      embedder: {
        provider: "openai",
        config: { apiKey: "k", model: "text-embedding-3-small" },
      },
      vectorStore: {
        provider: "memory",
        config: {
          collectionName: "et-gate-link",
          dimension: 1536,
          dbPath: ":memory:",
        },
      },
      llm: { provider: "openai", config: { apiKey: "k", model: "gpt-5-mini" } },
      historyDbPath: ":memory:",
    }) as any;

    (extractEntities as jest.Mock).mockReturnValue([
      { text: "Python", type: "animal" },
    ]);

    const entityStore = {
      search: jest.fn().mockResolvedValue([
        {
          id: "existing-1",
          score: 0.99,
          payload: {
            data: "Python",
            entityType: "language",
            linkedMemoryIds: ["mem-A"],
          },
        },
      ]),
      update: jest.fn().mockResolvedValue(undefined),
      insert: jest.fn().mockResolvedValue(undefined),
      list: jest.fn().mockResolvedValue([[]]),
    };

    m.getEntityStore = jest.fn().mockResolvedValue(entityStore);
    m._existingEntitiesByText = jest.fn().mockResolvedValue(new Map());

    await m._linkEntitiesForMemory("mem-B", "Python the snake", {
      user_id: "u1",
    });

    expect(entityStore.update).not.toHaveBeenCalled();
    expect(entityStore.insert).toHaveBeenCalledTimes(1);
    const payloads = entityStore.insert.mock.calls[0][2];
    expect(payloads[0].entityType).toBe("animal");
    expect(payloads[0].linkedMemoryIds).toEqual(["mem-B"]);
  });

  test("_linkEntitiesForMemory merges when existing type is missing (compat)", async () => {
    const m = new Memory({
      version: "v1.1",
      embedder: {
        provider: "openai",
        config: { apiKey: "k", model: "text-embedding-3-small" },
      },
      vectorStore: {
        provider: "memory",
        config: {
          collectionName: "et-gate-compat",
          dimension: 1536,
          dbPath: ":memory:",
        },
      },
      llm: { provider: "openai", config: { apiKey: "k", model: "gpt-5-mini" } },
      historyDbPath: ":memory:",
    }) as any;

    (extractEntities as jest.Mock).mockReturnValue([
      { text: "Python", type: "language" },
    ]);

    const entityStore = {
      search: jest.fn().mockResolvedValue([
        {
          id: "existing-2",
          score: 0.99,
          payload: {
            data: "Python",
            linkedMemoryIds: ["mem-A"],
          },
        },
      ]),
      update: jest.fn().mockResolvedValue(undefined),
      insert: jest.fn().mockResolvedValue(undefined),
      list: jest.fn().mockResolvedValue([[]]),
    };

    m.getEntityStore = jest.fn().mockResolvedValue(entityStore);
    m._existingEntitiesByText = jest.fn().mockResolvedValue(new Map());

    await m._linkEntitiesForMemory("mem-B", "Python the language", {
      user_id: "u1",
    });

    expect(entityStore.insert).not.toHaveBeenCalled();
    expect(entityStore.update).toHaveBeenCalledTimes(1);
    const updatedPayload = entityStore.update.mock.calls[0][2];
    expect(updatedPayload.entityType).toBe("language");
    expect(updatedPayload.linkedMemoryIds).toEqual(
      expect.arrayContaining(["mem-A", "mem-B"]),
    );
  });
});
