/**
 * Entity lookup failure handling (#6925).
 *
 * When the entity store's semantic `search()` throws (network blip, rate
 * limit, collection briefly unavailable), a failed lookup must NOT be treated
 * as "no matching entity exists". The old code swallowed the error with an
 * empty `catch {}`, leaving `matches = []`, which fell through to the insert
 * branch and created a duplicate entity row — silently forking the graph.
 *
 * Correct behaviour: warn and skip the entity, leaving any existing row alone.
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
        collectionName: `test-entity-fail-${Date.now()}-${Math.random()}`,
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

/**
 * Build a mock entity store with no pre-existing rows, so every extracted
 * entity misses the exact-match map and reaches the semantic `search()` path.
 */
function makeEntityStore(search: jest.Mock) {
  return {
    // No existing entities → exactMatches map is empty.
    list: jest.fn().mockResolvedValue([[], null]),
    search,
    insert: jest.fn().mockResolvedValue(undefined),
    update: jest.fn().mockResolvedValue(undefined),
    initialize: jest.fn().mockResolvedValue(undefined),
  };
}

describe("Entity lookup failure handling (#6925)", () => {
  let memory: Memory;
  let warnSpy: jest.SpyInstance;

  beforeEach(() => {
    memory = createMemory();
    warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(async () => {
    warnSpy.mockRestore();
    await memory.reset();
  });

  it("skips the entity (no duplicate insert) and warns when search() throws", async () => {
    const m = memory as any;
    await m._ensureInitialized();
    m.embedder.embed = jest.fn().mockResolvedValue(mockEmbedding);

    const search = jest
      .fn()
      .mockRejectedValue(new Error("entity store temporarily unavailable"));
    const entityStore = makeEntityStore(search);
    m._entityStore = entityStore;

    // Two proper entities are extracted from this text.
    await m._linkEntitiesForMemory("mem-1", "John Smith met Jane Doe", {
      user_id: "u1",
    });

    // The lookup failed, so we must NOT insert a competing row.
    expect(search).toHaveBeenCalled();
    expect(entityStore.insert).not.toHaveBeenCalled();
    expect(entityStore.update).not.toHaveBeenCalled();
    // And the failure must be surfaced, not swallowed silently.
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("skipping to avoid a duplicate entity row"),
    );
  });

  it("still inserts a new entity when search() legitimately returns no match", async () => {
    const m = memory as any;
    await m._ensureInitialized();
    m.embedder.embed = jest.fn().mockResolvedValue(mockEmbedding);

    // Healthy store that simply finds nothing → new entity should be inserted.
    const search = jest.fn().mockResolvedValue([]);
    const entityStore = makeEntityStore(search);
    m._entityStore = entityStore;

    await m._linkEntitiesForMemory("mem-1", "John Smith met Jane Doe", {
      user_id: "u1",
    });

    expect(search).toHaveBeenCalled();
    expect(entityStore.insert).toHaveBeenCalled();
  });
});
