/// <reference types="jest" />
/**
 * Verifies the memory pipeline threads the correct memory action
 * ("add" | "update" | "search") into the embedder. Task-type-aware providers
 * (e.g. Vertex AI) embed queries and documents differently based on this, and
 * the argument is silently ignored by every other embedder, so only a
 * pipeline-level test catches a dropped action.
 */
import { Memory } from "../src/memory";

const mockEmbedding = new Array(1536).fill(0.1);
// Prefixed `mock*` so jest's hoisted module factory may reference them.
const mockEmbed = jest.fn().mockResolvedValue(mockEmbedding);
const mockEmbedBatch = jest
  .fn()
  .mockImplementation((texts: string[]) =>
    Promise.resolve(texts.map(() => mockEmbedding)),
  );

const mockGenerateResponse = jest
  .fn()
  .mockResolvedValue(JSON.stringify({ memory: [] }));

jest.mock("../src/embeddings/google", () => ({ GoogleEmbedder: jest.fn() }));
jest.mock("../src/llms/google", () => ({ GoogleLLM: jest.fn() }));
jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: mockGenerateResponse,
  })),
}));
jest.mock("../src/embeddings/openai", () => ({
  OpenAIEmbedder: jest.fn().mockImplementation(() => ({
    embed: mockEmbed,
    embedBatch: mockEmbedBatch,
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
        collectionName: `test-action-${Date.now()}-${Math.random()}`,
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

describe("embedder memory-action threading", () => {
  let memory: Memory;

  beforeEach(() => {
    memory = createMemory();
    mockEmbed.mockClear();
    mockEmbedBatch.mockClear();
    mockGenerateResponse.mockResolvedValue(JSON.stringify({ memory: [] }));
  });

  afterEach(async () => {
    await memory.reset();
  });

  test("search() embeds the query with the 'search' action", async () => {
    await memory.search("what do I like", { filters: { user_id: "u1" } });
    expect(mockEmbed).toHaveBeenCalledWith("what do I like", "search");
  });

  test("update() embeds the new value with the 'update' action", async () => {
    // Missing id: update embeds the value before it throws on the absent row.
    await memory.update("missing-id", "new value").catch(() => {});
    expect(mockEmbed).toHaveBeenCalledWith("new value", "update");
  });

  test("add() batch-embeds extracted memories and entities with the 'add' action", async () => {
    mockGenerateResponse.mockResolvedValue(
      JSON.stringify({
        memory: [
          { id: "1", text: "John loves sci-fi movies", attributed_to: "user" },
        ],
      }),
    );

    await memory.add("I love sci-fi movies", { userId: "u1" });

    // Phase 1 retrieval embeds the incoming turn as a query.
    expect(mockEmbed).toHaveBeenCalledWith(
      expect.stringContaining("I love sci-fi movies"),
      "search",
    );
    // Phase 3 (extracted memories) and phase 7 (linked entities) both batch
    // embed as documents. Without an explicit action, a task-type-aware
    // embedder falls back to its own default and silently mis-embeds.
    expect(mockEmbedBatch).toHaveBeenCalledWith(
      ["John loves sci-fi movies"],
      "add",
    );
    expect(mockEmbedBatch.mock.calls.length).toBeGreaterThan(0);
    for (const call of mockEmbedBatch.mock.calls) {
      expect(call[1]).toBe("add");
    }
  });
});
