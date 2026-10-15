/**
 * A failed entity lookup must not be treated as "no match found".
 *
 * Both entity-linking paths wrapped `entityStore.search()` in an empty catch,
 * so a store error left `matches` empty and control fell through to the branch
 * that inserts a new entity row. The result was a duplicate row instead of a
 * link to the row that already existed, with nothing logged.
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
        memory: [{ id: "0", text: "Alice met Bob", attributed_to: "user" }],
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

function makeEntityStore(searchImpl: () => Promise<any[]>) {
  return {
    initialize: jest.fn().mockResolvedValue(undefined),
    list: jest.fn().mockResolvedValue([]),
    search: jest.fn().mockImplementation(searchImpl),
    insert: jest.fn().mockResolvedValue(undefined),
    update: jest.fn().mockResolvedValue(undefined),
  };
}

const throwing = () => Promise.reject(new Error("entity store unavailable"));
const empty = () => Promise.resolve([]);

describe("entity search failures are not treated as no-match", () => {
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

  it("skips the entity instead of inserting a duplicate when the lookup throws", async () => {
    const m = memory as any;
    await m._ensureInitialized();
    const store = makeEntityStore(throwing);
    m._entityStore = store;

    await m._linkEntitiesForMemory("mem-1", "Alice met Bob", {
      user_id: "u1",
    });

    expect(store.search).toHaveBeenCalled();
    expect(store.insert).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
  });

  it("skips the entity in the add pipeline when the lookup throws", async () => {
    const m = memory as any;
    await m._ensureInitialized();
    const store = makeEntityStore(throwing);
    m._entityStore = store;

    await m.addToVectorStore(
      [{ role: "user", content: "Alice met Bob" }],
      {},
      { user_id: "u1" },
      true,
    );

    expect(store.search).toHaveBeenCalled();
    expect(store.insert).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
  });

  it("still inserts when the lookup succeeds and genuinely finds nothing", async () => {
    const m = memory as any;
    await m._ensureInitialized();
    const store = makeEntityStore(empty);
    m._entityStore = store;

    await m._linkEntitiesForMemory("mem-1", "Alice met Bob", {
      user_id: "u1",
    });

    expect(store.search).toHaveBeenCalled();
    expect(store.insert).toHaveBeenCalled();
    expect(warnSpy).not.toHaveBeenCalled();
  });
});
