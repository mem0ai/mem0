/**
 * Entity failure observability (#6795).
 *
 * Entity linking/cleanup failures used to be logged with console.debug, which
 * is filtered out by most production log configs. Retrieval quality then
 * degrades quietly. These failures must surface at console.warn.
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
          {
            id: "0",
            text: "Alice works at OpenAI",
            attributed_to: "user",
          },
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
        collectionName: `test-entity-log-${Date.now()}-${Math.random()}`,
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

describe("Entity failure log level (#6795)", () => {
  let memory: Memory;
  let warnSpy: jest.SpyInstance;
  let debugSpy: jest.SpyInstance;

  beforeEach(() => {
    memory = createMemory();
    warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    debugSpy = jest.spyOn(console, "debug").mockImplementation(() => {});
  });

  afterEach(async () => {
    warnSpy.mockRestore();
    debugSpy.mockRestore();
    jest.restoreAllMocks();
    await memory.reset();
  });

  it("warns when entity embed fails during _linkEntitiesForMemory", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    m._entityStore = {
      list: jest.fn().mockResolvedValue([]),
      search: jest.fn().mockResolvedValue([]),
      insert: jest.fn().mockResolvedValue(undefined),
      update: jest.fn().mockResolvedValue(undefined),
      delete: jest.fn().mockResolvedValue(undefined),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
    m.embedder = {
      embed: jest.fn().mockRejectedValue(new Error("embed down")),
      embedBatch: jest.fn().mockRejectedValue(new Error("embed down")),
    };

    await m._linkEntitiesForMemory("mem-1", "Alice works at OpenAI", {
      user_id: "u1",
    });

    const messages = warnSpy.mock.calls.map((c) => String(c[0])).join("\n");
    expect(messages).toMatch(/Entity embed failed/);
    const debugMessages = debugSpy.mock.calls.map((c) => String(c[0])).join("\n");
    expect(debugMessages).not.toMatch(/Entity embed failed/);
  });

  it("warns when entity re-embed fails during cleanup", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    m._entityStore = {
      list: jest.fn().mockResolvedValue([
        {
          id: "ent-1",
          payload: {
            data: "Alice",
            linkedMemoryIds: ["mem-1", "mem-2"],
          },
        },
      ]),
      search: jest.fn().mockResolvedValue([]),
      insert: jest.fn().mockResolvedValue(undefined),
      update: jest.fn().mockResolvedValue(undefined),
      delete: jest.fn().mockResolvedValue(undefined),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
    m.embedder = {
      embed: jest.fn().mockRejectedValue(new Error("re-embed down")),
      embedBatch: jest.fn().mockRejectedValue(new Error("re-embed down")),
    };

    await m._removeMemoryFromEntityStore("mem-1", { user_id: "u1" });

    const messages = warnSpy.mock.calls.map((c) => String(c[0])).join("\n");
    expect(messages).toMatch(/Entity re-embed failed/);
    const debugMessages = debugSpy.mock.calls.map((c) => String(c[0])).join("\n");
    expect(debugMessages).not.toMatch(/Entity re-embed failed/);
  });

  it("warns when entity insert fails during _linkEntitiesForMemory", async () => {
    const m = memory as any;
    await m._ensureInitialized();

    m._entityStore = {
      list: jest.fn().mockResolvedValue([]),
      search: jest.fn().mockResolvedValue([]),
      insert: jest.fn().mockRejectedValue(new Error("insert down")),
      update: jest.fn().mockResolvedValue(undefined),
      delete: jest.fn().mockResolvedValue(undefined),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
    m.embedder = {
      embed: jest.fn().mockResolvedValue(mockEmbedding),
      embedBatch: jest
        .fn()
        .mockImplementation((texts: string[]) =>
          Promise.resolve(texts.map(() => mockEmbedding)),
        ),
    };

    await m._linkEntitiesForMemory("mem-1", "Alice works at OpenAI", {
      user_id: "u1",
    });

    const messages = warnSpy.mock.calls.map((c) => String(c[0])).join("\n");
    expect(messages).toMatch(/Entity insert failed/);
    const debugMessages = debugSpy.mock.calls.map((c) => String(c[0])).join("\n");
    expect(debugMessages).not.toMatch(/Entity insert failed/);
  });
});
