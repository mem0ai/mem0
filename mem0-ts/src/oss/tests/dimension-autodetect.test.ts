/// <reference types="jest" />
/**
 * Tests for embedding dimension auto-detection.
 *
 * Covers:
 *  - ConfigManager: dimension resolution logic
 *  - Memory class: probe-based auto-detection, lazy init gate, backward compat
 *  - MemoryVectorStore: backward compat with explicit dimensions
 *  - Explicit error messages on probe failure
 */

import { ConfigManager } from "../src/config/manager";
import { MemoryVectorStore } from "../src/vector_stores/memory";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

jest.setTimeout(15000);

// ───────────────────────────────────────────────────────────────────────────
// 1. ConfigManager – dimension resolution
// ───────────────────────────────────────────────────────────────────────────
describe("ConfigManager – dimension resolution", () => {
  const baseLlm = { provider: "openai", config: { apiKey: "k" } };

  it("leaves dimension undefined when nothing explicit is set", () => {
    const cfg = ConfigManager.mergeConfig({
      embedder: { provider: "openai", config: { apiKey: "k" } },
      vectorStore: { provider: "memory", config: { collectionName: "t" } },
      llm: baseLlm,
    });
    expect(cfg.vectorStore.config.dimension).toBeUndefined();
  });

  it("uses embeddingDims from embedder config", () => {
    const cfg = ConfigManager.mergeConfig({
      embedder: {
        provider: "ollama",
        config: { model: "nomic-embed-text", embeddingDims: 768 },
      },
      vectorStore: { provider: "qdrant", config: { collectionName: "t" } },
      llm: baseLlm,
    });
    expect(cfg.vectorStore.config.dimension).toBe(768);
  });

  it("prefers explicit vectorStore.dimension over embeddingDims", () => {
    const cfg = ConfigManager.mergeConfig({
      embedder: {
        provider: "ollama",
        config: { model: "nomic-embed-text", embeddingDims: 768 },
      },
      vectorStore: {
        provider: "qdrant",
        config: { collectionName: "t", dimension: 1024 },
      },
      llm: baseLlm,
    });
    expect(cfg.vectorStore.config.dimension).toBe(1024);
  });

  it("leaves dimension undefined for custom client without explicit dims", () => {
    const cfg = ConfigManager.mergeConfig({
      embedder: { provider: "ollama", config: { model: "nomic-embed-text" } },
      vectorStore: {
        provider: "qdrant",
        config: { collectionName: "t", client: {} },
      },
      llm: baseLlm,
    });
    expect(cfg.vectorStore.config.dimension).toBeUndefined();
  });

  it("uses embeddingDims with a custom client", () => {
    const cfg = ConfigManager.mergeConfig({
      embedder: {
        provider: "ollama",
        config: { model: "nomic-embed-text", embeddingDims: 768 },
      },
      vectorStore: {
        provider: "qdrant",
        config: { collectionName: "t", client: {} },
      },
      llm: baseLlm,
    });
    expect(cfg.vectorStore.config.dimension).toBe(768);
  });

  it("preserves all other vectorStore config fields", () => {
    const cfg = ConfigManager.mergeConfig({
      embedder: { provider: "openai", config: { apiKey: "k" } },
      vectorStore: {
        provider: "qdrant",
        config: {
          collectionName: "my-coll",
          host: "my-host",
          port: 6333,
          apiKey: "qdrant-key",
        },
      },
      llm: baseLlm,
    });
    expect(cfg.vectorStore.config.collectionName).toBe("my-coll");
    expect(cfg.vectorStore.config.host).toBe("my-host");
    expect(cfg.vectorStore.config.port).toBe(6333);
    expect(cfg.vectorStore.config.apiKey).toBe("qdrant-key");
  });

  it("leaves dimension undefined with empty config", () => {
    const cfg = ConfigManager.mergeConfig({
      embedder: { provider: "openai", config: {} },
      vectorStore: { provider: "memory", config: {} },
      llm: baseLlm,
    });
    expect(cfg.vectorStore.config.dimension).toBeUndefined();
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 2. MemoryVectorStore – backward compat with explicit dimensions
// ───────────────────────────────────────────────────────────────────────────
describe("MemoryVectorStore – backward compat", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-test-"));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("defaults to dimension 1536 when not specified", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dbPath: path.join(tmpDir, "vs.db"),
    });

    const vector = new Array(1536).fill(0.1);
    await store.insert([vector], ["id-1"], [{ data: "hello" }]);
    const result = await store.get("id-1");
    expect(result).not.toBeNull();
  });

  it("explicit dimension=1536 still works", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dimension: 1536,
      dbPath: path.join(tmpDir, "vs.db"),
    });

    const vector = new Array(1536).fill(0.1);
    await store.insert([vector], ["id-1"], [{ data: "hello" }]);
    const result = await store.get("id-1");
    expect(result).not.toBeNull();
  });

  it("explicit dimension rejects mismatched vectors", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dimension: 1536,
      dbPath: path.join(tmpDir, "vs.db"),
    });

    const wrongVector = new Array(768).fill(0.1);
    await expect(
      store.insert([wrongVector], ["id-1"], [{ data: "hello" }]),
    ).rejects.toThrow("Vector dimension mismatch");
  });

  it("search validates dimension", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dimension: 4,
      dbPath: path.join(tmpDir, "vs.db"),
    });

    await expect(store.search([1, 2, 3], 1)).rejects.toThrow(
      "Query dimension mismatch",
    );
  });

  it("custom dimension=768 works end-to-end", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dimension: 768,
      dbPath: path.join(tmpDir, "vs.db"),
    });

    await store.insert(
      [
        [1, ...new Array(767).fill(0)],
        [0, 1, ...new Array(766).fill(0)],
      ],
      ["a", "b"],
      [{ data: "alpha" }, { data: "beta" }],
    );

    const results = await store.search([1, ...new Array(767).fill(0)], 2);
    expect(results.length).toBe(2);
    expect(results[0].id).toBe("a");
  });

  it("getUserId and setUserId still work", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dbPath: path.join(tmpDir, "vs.db"),
    });

    const userId = await store.getUserId();
    expect(typeof userId).toBe("string");
    expect(userId.length).toBeGreaterThan(0);

    await store.setUserId("custom-user");
    const newUserId = await store.getUserId();
    expect(newUserId).toBe("custom-user");
  });

  it("initialize() is idempotent", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dbPath: path.join(tmpDir, "vs.db"),
    });

    await store.initialize();
    await store.initialize();
    await store.initialize();
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 3. Memory class – auto-init with probe, lazy gate, backward compat
// ───────────────────────────────────────────────────────────────────────────
describe("Memory – auto-initialization", () => {
  let mockEmbedderFactory: any;
  let mockVectorStoreFactory: any;
  let mockLlmFactory: any;
  let mockHistoryFactory: any;
  let MemoryClass: any;

  function createMockEmbedder(dims: number) {
    return {
      embed: jest.fn().mockResolvedValue(new Array(dims).fill(0)),
      embedBatch: jest.fn().mockResolvedValue([new Array(dims).fill(0)]),
    };
  }

  function createMockVectorStore() {
    return {
      insert: jest.fn().mockResolvedValue(undefined),
      search: jest.fn().mockResolvedValue([]),
      get: jest.fn().mockResolvedValue(null),
      update: jest.fn().mockResolvedValue(undefined),
      delete: jest.fn().mockResolvedValue(undefined),
      deleteCol: jest.fn().mockResolvedValue(undefined),
      list: jest.fn().mockResolvedValue([[], 0]),
      getUserId: jest.fn().mockResolvedValue("test-user-id"),
      setUserId: jest.fn().mockResolvedValue(undefined),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
  }

  beforeEach(() => {
    jest.resetModules();

    const mockEmbedder = createMockEmbedder(768);
    const mockVStore = createMockVectorStore();

    mockEmbedderFactory = { create: jest.fn().mockReturnValue(mockEmbedder) };
    mockVectorStoreFactory = { create: jest.fn().mockReturnValue(mockVStore) };
    mockLlmFactory = {
      create: jest.fn().mockReturnValue({
        generateResponse: jest.fn().mockResolvedValue('{"facts":[]}'),
      }),
    };
    mockHistoryFactory = {
      create: jest.fn().mockReturnValue({
        addHistory: jest.fn().mockResolvedValue(undefined),
        getHistory: jest.fn().mockResolvedValue([]),
        reset: jest.fn().mockResolvedValue(undefined),
      }),
    };

    jest.doMock("../src/utils/factory", () => ({
      EmbedderFactory: mockEmbedderFactory,
      VectorStoreFactory: mockVectorStoreFactory,
      LLMFactory: mockLlmFactory,
      HistoryManagerFactory: mockHistoryFactory,
    }));

    jest.doMock("../src/utils/telemetry", () => ({
      captureClientEvent: jest.fn().mockResolvedValue(undefined),
    }));

    MemoryClass = require("../src/memory").Memory;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("probes embedder to detect dimension when none set", async () => {
    const mockEmbedder = createMockEmbedder(768);
    const mockVStore = createMockVectorStore();
    mockEmbedderFactory.create.mockReturnValue(mockEmbedder);
    mockVectorStoreFactory.create.mockReturnValue(mockVStore);

    const mem = new MemoryClass({
      embedder: { provider: "ollama", config: { model: "nomic-embed-text" } },
      vectorStore: { provider: "qdrant", config: { collectionName: "test" } },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    await mem.getAll({ filters: { user_id: "u1" } });

    // Should have called embed("dimension probe") to detect dimension
    expect(mockEmbedder.embed).toHaveBeenCalledWith("dimension probe");

    // VectorStoreFactory should have been called with detected dimension
    const vsCreateCall = mockVectorStoreFactory.create.mock.calls[0];
    expect(vsCreateCall[1].dimension).toBe(768);
  });

  it("skips probe when explicit dimension provided", async () => {
    const mockEmbedder = createMockEmbedder(1536);
    const mockVStore = createMockVectorStore();
    mockEmbedderFactory.create.mockReturnValue(mockEmbedder);
    mockVectorStoreFactory.create.mockReturnValue(mockVStore);

    const mem = new MemoryClass({
      embedder: { provider: "openai", config: { apiKey: "k" } },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test", dimension: 1536 },
      },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    await mem.getAll({ filters: { user_id: "u1" } });

    // embed should NOT have been called for probing
    expect(mockEmbedder.embed).not.toHaveBeenCalledWith("dimension probe");

    // VectorStoreFactory gets the explicit dimension
    const vsCreateCall = mockVectorStoreFactory.create.mock.calls[0];
    expect(vsCreateCall[1].dimension).toBe(1536);
  });

  it("skips probe when embeddingDims provided", async () => {
    const mockEmbedder = createMockEmbedder(768);
    const mockVStore = createMockVectorStore();
    mockEmbedderFactory.create.mockReturnValue(mockEmbedder);
    mockVectorStoreFactory.create.mockReturnValue(mockVStore);

    const mem = new MemoryClass({
      embedder: {
        provider: "ollama",
        config: { model: "nomic-embed-text", embeddingDims: 768 },
      },
      vectorStore: { provider: "qdrant", config: { collectionName: "test" } },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    await mem.getAll({ filters: { user_id: "u1" } });

    // ConfigManager resolves dimension from embeddingDims → no probe needed
    expect(mockEmbedder.embed).not.toHaveBeenCalledWith("dimension probe");
  });

  it("all public methods wait for initialization", async () => {
    let resolveProbe: () => void;
    let probeCallCount = 0;
    const mockEmbedder = {
      embed: jest.fn().mockImplementation(() => {
        probeCallCount++;
        if (probeCallCount === 1) {
          // First call is the dimension probe — hang until manually resolved
          return new Promise<number[]>((resolve) => {
            resolveProbe = () => resolve(new Array(768).fill(0));
          });
        }
        // Subsequent calls (from search, etc.) resolve immediately
        return Promise.resolve(new Array(768).fill(0));
      }),
      embedBatch: jest.fn(),
    };
    const mockVStore = createMockVectorStore();
    mockEmbedderFactory.create.mockReturnValue(mockEmbedder);
    mockVectorStoreFactory.create.mockReturnValue(mockVStore);

    const mem = new MemoryClass({
      embedder: { provider: "ollama", config: { model: "test" } },
      vectorStore: { provider: "qdrant", config: { collectionName: "t" } },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    let getAllDone = false;
    let searchDone = false;
    let getDone = false;

    const getAllP = mem
      .getAll({ filters: { user_id: "u" } })
      .then(() => (getAllDone = true));
    const searchP = mem
      .search("q", { filters: { user_id: "u" } })
      .then(() => (searchDone = true));
    const getP = mem.get("id").then(() => (getDone = true));

    await new Promise((r) => setTimeout(r, 50));
    expect(getAllDone).toBe(false);
    expect(searchDone).toBe(false);
    expect(getDone).toBe(false);

    // Resolve the probe — init completes — methods unblock
    resolveProbe!();
    await Promise.all([getAllP, searchP, getP]);
    expect(getAllDone).toBe(true);
    expect(searchDone).toBe(true);
    expect(getDone).toBe(true);
  });

  it("reset re-creates vector store with correct dimension", async () => {
    const mockEmbedder = createMockEmbedder(768);
    const mockVStore = createMockVectorStore();
    mockEmbedderFactory.create.mockReturnValue(mockEmbedder);
    mockVectorStoreFactory.create.mockReturnValue(mockVStore);

    const mem = new MemoryClass({
      embedder: { provider: "ollama", config: { model: "nomic-embed-text" } },
      vectorStore: { provider: "qdrant", config: { collectionName: "test" } },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    await mem.getAll({ filters: { user_id: "u1" } });
    expect(mockVectorStoreFactory.create).toHaveBeenCalledTimes(1);

    // Reset should re-create vector store
    const mockVStore2 = createMockVectorStore();
    mockVectorStoreFactory.create.mockReturnValue(mockVStore2);
    await mem.reset();
    expect(mockVectorStoreFactory.create).toHaveBeenCalledTimes(2);

    // Second creation should still have dimension=768 (cached from first probe)
    const secondCall = mockVectorStoreFactory.create.mock.calls[1];
    expect(secondCall[1].dimension).toBe(768);
  });

  it("backward compat: full explicit config works without probe", async () => {
    const mockEmbedder = createMockEmbedder(1536);
    const mockVStore = createMockVectorStore();
    mockEmbedderFactory.create.mockReturnValue(mockEmbedder);
    mockVectorStoreFactory.create.mockReturnValue(mockVStore);

    const mem = new MemoryClass({
      version: "v1.1",
      embedder: {
        provider: "openai",
        config: { apiKey: "sk-fake", model: "text-embedding-3-small" },
      },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test-memories", dimension: 1536 },
      },
      llm: {
        provider: "openai",
        config: { apiKey: "sk-fake", model: "gpt-5-mini" },
      },
      historyDbPath: ":memory:",
      disableHistory: true,
    });

    await mem.getAll({ filters: { user_id: "u1" } });
    expect(mockEmbedder.embed).not.toHaveBeenCalledWith("dimension probe");
  });

  it("throws explicit error when probe fails", async () => {
    const mockEmbedder = {
      embed: jest.fn().mockRejectedValue(new Error("Connection refused")),
      embedBatch: jest.fn(),
    };
    mockEmbedderFactory.create.mockReturnValue(mockEmbedder);

    // Suppress console.error for this test
    const consoleSpy = jest
      .spyOn(console, "error")
      .mockImplementation(() => {});

    const mem = new MemoryClass({
      embedder: { provider: "ollama", config: { model: "nomic-embed-text" } },
      vectorStore: { provider: "qdrant", config: { collectionName: "test" } },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    // getAll should reject with the init error
    await expect(mem.getAll({ filters: { user_id: "u1" } })).rejects.toThrow(
      "auto-detect embedding dimension",
    );

    // Verify the error was logged and contains helpful information
    const errorCall = consoleSpy.mock.calls.find(
      (call) =>
        call[0] instanceof Error &&
        call[0].message.includes("auto-detect embedding dimension"),
    );
    expect(errorCall).toBeDefined();
    const errorMsg = (errorCall![0] as Error).message;
    expect(errorMsg).toContain("ollama");
    expect(errorMsg).toContain("Connection refused");
    expect(errorMsg).toContain("dimension");
    expect(errorMsg).toContain("embeddingDims");

    consoleSpy.mockRestore();
  });
});
