/**
 * Tests for SQLite resilience fixes:
 * 1. disableHistory config passthrough
 * 2. initPromise poisoning fix (retry after failure)
 * 3. Graceful SQLite fallback in OSSProvider
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mem0ConfigSchema, createProvider } from "./index.ts";

/** Stub vector-store classes required by OSSProvider._init's patching loop. */
function vectorStubs() {
  return {
    PGVector: class { initialize() { return Promise.resolve(); } },
    RedisDB: class { initialize() { return Promise.resolve(); } },
    Qdrant: class { initialize() { return Promise.resolve(); } },
  };
}

// ---------------------------------------------------------------------------
// 1. Config: disableHistory passthrough
// ---------------------------------------------------------------------------
describe("mem0ConfigSchema — disableHistory", () => {
  const baseConfig = {
    mode: "open-source",
    oss: {
      embedder: { provider: "openai", config: { apiKey: "sk-test" } },
    },
  };

  it("preserves oss.disableHistory: true through config parsing", () => {
    const cfg = mem0ConfigSchema.parse({
      ...baseConfig,
      oss: { ...baseConfig.oss, disableHistory: true },
    });
    expect(cfg.oss?.disableHistory).toBe(true);
  });

  it("preserves oss.disableHistory: false through config parsing", () => {
    const cfg = mem0ConfigSchema.parse({
      ...baseConfig,
      oss: { ...baseConfig.oss, disableHistory: false },
    });
    expect(cfg.oss?.disableHistory).toBe(false);
  });

  it("omits disableHistory when not provided", () => {
    const cfg = mem0ConfigSchema.parse(baseConfig);
    expect(cfg.oss?.disableHistory).toBeUndefined();
  });

  it("does not reject unknown keys inside oss object", () => {
    // oss sub-object is passed through resolveEnvVarsDeep, not key-checked
    expect(() =>
      mem0ConfigSchema.parse({
        ...baseConfig,
        oss: { ...baseConfig.oss, disableHistory: true },
      }),
    ).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// 2. OSSProvider: disableHistory flows to Memory constructor
// ---------------------------------------------------------------------------
describe("OSSProvider — disableHistory passthrough to Memory", () => {
  let capturedConfig: Record<string, unknown> | undefined;
  let memoryCallCount: number;

  beforeEach(() => {
    capturedConfig = undefined;
    memoryCallCount = 0;
    vi.resetModules();

    vi.doMock("mem0ai/oss", () => ({
      Memory: class MockMemory {
        constructor(config: Record<string, unknown>) {
          memoryCallCount++;
          capturedConfig = { ...config };
        }
        async add() {
          return { results: [] };
        }
        async search() {
          return { results: [] };
        }
        async get() {
          return {};
        }
        async getAll() {
          return [];
        }
        async delete() {}
      },
      ...vectorStubs(),
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("passes disableHistory: true to Memory when configured", async () => {
    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: { disableHistory: true },
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    // Trigger lazy init by calling search
    try {
      await provider.search("test", { user_id: "u1" });
    } catch {
      /* provider may fail on mock, that's ok */
    }

    expect(capturedConfig).toBeDefined();
    expect(capturedConfig!.disableHistory).toBe(true);
  });

  it("does not set disableHistory when not configured and sqlite works", async () => {
    // Mock better-sqlite3 so the proactive probe succeeds
    vi.doMock("better-sqlite3", () => {
      return { default: class { close() {} } };
    });

    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: {},
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    try {
      await provider.search("test", { user_id: "u1" });
    } catch {}

    expect(capturedConfig).toBeDefined();
    expect(capturedConfig!.disableHistory).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// 3. OSSProvider: initPromise is cleared on failure (allows retry)
// ---------------------------------------------------------------------------
describe("OSSProvider — initPromise retry after failure", () => {
  let callCount: number;

  beforeEach(() => {
    callCount = 0;
    vi.resetModules();

    vi.doMock("mem0ai/oss", () => ({
      Memory: class MockMemory {
        constructor() {
          callCount++;
          if (callCount === 1) {
            throw new Error("SQLITE_CANTOPEN: simulated binding failure");
          }
          // Second+ call succeeds
        }
        async search() {
          return { results: [] };
        }
        async get() {
          return {};
        }
        async getAll() {
          return [];
        }
        async add() {
          return { results: [] };
        }
        async delete() {}
      },
      ...vectorStubs(),
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("retries initialization after a transient failure", async () => {
    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: { disableHistory: true },
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    // First call: _init throws, but initPromise is cleared so retry is possible
    await expect(provider.search("test", { user_id: "u1" })).rejects.toThrow(
      "SQLITE_CANTOPEN",
    );

    // Second call: should retry _init (not return cached rejection)
    // callCount === 1 threw, so callCount === 2 should succeed
    const results = await provider.search("test", { user_id: "u1" });
    expect(results).toBeDefined();
    expect(callCount).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// 4. OSSProvider: graceful fallback disables history on init failure
// ---------------------------------------------------------------------------
describe("OSSProvider — graceful SQLite fallback", () => {
  let capturedConfigs: Record<string, unknown>[];
  /** When set, the mock Memory constructor always throws with this message. */
  let forceConstructorError: string | null;

  beforeEach(() => {
    capturedConfigs = [];
    forceConstructorError = null;
    vi.resetModules();

    vi.doMock("mem0ai/oss", () => ({
      Memory: class MockMemory {
        constructor(config: Record<string, unknown>) {
          capturedConfigs.push({ ...config });
          if (forceConstructorError) {
            throw new Error(forceConstructorError);
          }
          if (!config.disableHistory) {
            throw new Error("Could not locate the bindings file");
          }
          // Succeeds when disableHistory is true
        }
        async search() {
          return { results: [] };
        }
        async get() {
          return {};
        }
        async getAll() {
          return [];
        }
        async add() {
          return { results: [] };
        }
        async delete() {}
      },
      ...vectorStubs(),
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("retries with disableHistory: true when initial construction fails", async () => {
    // Mock better-sqlite3 so the proactive probe succeeds — tests the
    // catch-retry fallback path for other constructor errors.
    vi.doMock("better-sqlite3", () => {
      return { default: class { close() {} } };
    });

    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: {},
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    // Should succeed — first attempt fails, fallback with disableHistory succeeds
    const results = await provider.search("test", { user_id: "u1" });
    expect(results).toBeDefined();

    // Memory constructor was called twice
    expect(capturedConfigs).toHaveLength(2);
    expect(capturedConfigs[0].disableHistory).toBeFalsy();
    expect(capturedConfigs[1].disableHistory).toBe(true);

    // Warning was logged
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("[mem0] Memory initialization failed"),
      expect.stringContaining("bindings file"),
    );
    warnSpy.mockRestore();
  });

  it("proactively disables history when better-sqlite3 binary is broken", async () => {
    // Do NOT mock better-sqlite3 — let probe detect the real version mismatch
    // (or force it to fail if native binary happens to work on this Node).
    vi.doMock("better-sqlite3", () => {
      return { default: class { constructor() { throw new Error("NODE_MODULE_VERSION mismatch"); } } };
    });

    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: {},
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    const results = await provider.search("test", { user_id: "u1" });
    expect(results).toBeDefined();

    // Only ONE constructor call — probe detected broken sqlite, skipped retry
    expect(capturedConfigs).toHaveLength(1);
    expect(capturedConfigs[0].disableHistory).toBe(true);
  });

  it("does not retry when disableHistory is already true", async () => {
    // Force the constructor to always throw, regardless of disableHistory
    forceConstructorError = "vector store connection refused";

    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: { disableHistory: true },
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    // Should throw — no fallback possible when disableHistory was already set
    await expect(provider.search("test", { user_id: "u1" })).rejects.toThrow(
      "vector store connection refused",
    );
  });
});

// ---------------------------------------------------------------------------
// 5. PlatformProvider — initPromise retry after failure
// ---------------------------------------------------------------------------
describe("PlatformProvider — initPromise retry after failure", () => {
  let callCount: number;

  beforeEach(() => {
    callCount = 0;
    vi.resetModules();

    vi.doMock("mem0ai", () => ({
      default: class MockMemoryClient {
        constructor() {
          callCount++;
          if (callCount === 1) {
            throw new Error("Network timeout");
          }
        }
        async search() {
          return [];
        }
        async get() {
          return {};
        }
        async getAll() {
          return [];
        }
        async add() {
          return { results: [] };
        }
        async delete() {}
      },
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("retries initialization after a transient failure", async () => {
    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "platform",
      apiKey: "test-api-key",
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    // First call fails
    await expect(provider.search("test", { user_id: "u1" })).rejects.toThrow(
      "Network timeout",
    );

    // Second call should retry (not return cached rejection)
    const results = await provider.search("test", { user_id: "u1" });
    expect(results).toBeDefined();
    expect(callCount).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// 6. OSSProvider: _buildConfig covers all branches
// ---------------------------------------------------------------------------
describe("OSSProvider — _buildConfig branch coverage", () => {
  let capturedConfig: Record<string, unknown> | undefined;

  beforeEach(() => {
    capturedConfig = undefined;
    vi.resetModules();

    vi.doMock("mem0ai/oss", () => ({
      Memory: class MockMemory {
        constructor(config: Record<string, unknown>) {
          capturedConfig = { ...config };
        }
        async search() { return { results: [] }; }
        async get() { return {}; }
        async getAll() { return []; }
        async add() { return { results: [] }; }
        async delete() {}
      },
      ...vectorStubs(),
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("builds config with custom embedder, llm, vectorStore, and historyDbPath", async () => {
    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: {
        embedder: { provider: "openai", config: { apiKey: "sk-e", model: "text-embedding-3-small" } },
        llm: { provider: "openai", config: { apiKey: "sk-l", model: "gpt-4" } },
        vectorStore: { provider: "qdrant", config: { host: "localhost", port: 6333 } },
        historyDbPath: "/tmp/history.db",
        disableHistory: true,
      },
    });
    const api = { resolvePath: (p: string) => `/resolved${p}` } as any;
    const provider = createProvider(cfg, api);

    await provider.search("test", { user_id: "u1" });

    expect(capturedConfig).toBeDefined();
    expect(capturedConfig!.embedder).toEqual({
      provider: "openai",
      config: { model: "text-embedding-3-small", apiKey: "sk-e" },
    });
    expect(capturedConfig!.llm).toEqual({
      provider: "openai",
      config: expect.objectContaining({ model: "gpt-4", apiKey: "sk-l" }),
    });
    expect(capturedConfig!.vectorStore).toEqual({ provider: "qdrant", config: { host: "localhost", port: 6333 } });
    expect(capturedConfig!.historyDbPath).toBe("/resolved/tmp/history.db");
    expect(capturedConfig!.disableHistory).toBe(true);
  });

  it("strips empty-string values from embedder and llm config", async () => {
    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: {
        embedder: { provider: "openai", config: { apiKey: "", model: "custom-model" } },
        llm: { provider: "openai", config: { apiKey: "", model: "" } },
        disableHistory: true,
      },
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    await provider.search("test", { user_id: "u1" });

    expect(capturedConfig).toBeDefined();
    // Empty apiKey should be stripped, leaving only the non-empty model
    const embedderCfg = (capturedConfig!.embedder as any).config;
    expect(embedderCfg.apiKey).toBeUndefined();
    expect(embedderCfg.model).toBe("custom-model");
    // Both empty keys in llm should be stripped, defaults applied
    const llmCfg = (capturedConfig!.llm as any).config;
    expect(llmCfg.apiKey).toBeUndefined();
  });

  it("falls back to default provider when embedder/llm provider is empty", async () => {
    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: {
        embedder: { provider: "", config: { apiKey: "sk-e" } },
        llm: { provider: "", config: { apiKey: "sk-l" } },
        disableHistory: true,
      },
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    await provider.search("test", { user_id: "u1" });

    expect(capturedConfig).toBeDefined();
    // Empty provider should fall back to "openai" default
    expect((capturedConfig!.embedder as any).provider).toBe("openai");
    expect((capturedConfig!.llm as any).provider).toBe("openai");
  });
});

// ---------------------------------------------------------------------------
// 7. OSSProvider: vector store dimension patching
// ---------------------------------------------------------------------------
describe("OSSProvider — vector store dimension patching", () => {
  let capturedModule: any;

  beforeEach(() => {
    vi.resetModules();

    vi.doMock("mem0ai/oss", () => {
      const mod = {
        Memory: class MockMemory {
          constructor() {}
          async search() { return { results: [] }; }
          async get() { return {}; }
          async getAll() { return []; }
          async add() { return { results: [] }; }
          async delete() {}
        },
        PGVector: class {
          config: any;
          dimension: any;
          _initializePromise: any;
          initialize() { return Promise.resolve("pg-initialized"); }
        },
        RedisDB: class {
          config: any;
          _initializePromise: any;
          initialize() { return Promise.resolve("redis-initialized"); }
        },
        Qdrant: class {
          config: any;
          dimension: any;
          _initializePromise: any;
          initialize() { return Promise.resolve("qdrant-initialized"); }
        },
      };
      capturedModule = mod;
      return mod;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  async function triggerInit() {
    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: { disableHistory: true },
    });
    const provider = createProvider(cfg, { resolvePath: (p: string) => p } as any);
    await provider.search("test", { user_id: "u1" });
  }

  it("copies config.dimension to embeddingModelDims and this.dimension", async () => {
    await triggerInit();

    const pg = new capturedModule.PGVector();
    pg.config = { dimension: 1536 };
    await pg.initialize();

    expect(pg.config.embeddingModelDims).toBe(1536);
    expect(pg.dimension).toBe(1536);
  });

  it("returns resolved promise when no dimensions are known", async () => {
    await triggerInit();

    const pg = new capturedModule.PGVector();
    pg.config = {};
    const result = await pg.initialize();
    expect(result).toBeUndefined();
  });

  it("runs original initialize only once via cached promise", async () => {
    await triggerInit();

    const q = new capturedModule.Qdrant();
    q.config = { dimension: 768 };

    const first = await q.initialize();
    const second = await q.initialize();
    expect(first).toBe("qdrant-initialized");
    expect(second).toBe("qdrant-initialized");
    expect(q._initializePromise).toBeDefined();
  });

  it("skips missing vector store classes without crashing", async () => {
    // Override with a mock that omits PGVector entirely
    vi.resetModules();
    vi.doMock("mem0ai/oss", () => ({
      Memory: class {
        constructor() {}
        async search() { return { results: [] }; }
        async get() { return {}; }
        async getAll() { return []; }
        async add() { return { results: [] }; }
        async delete() {}
      },
      PGVector: undefined, // explicitly absent — tests the !VectorCls guard
      RedisDB: class { initialize() { return Promise.resolve(); } },
      Qdrant: class { initialize() { return Promise.resolve(); } },
    }));

    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: { disableHistory: true },
    });
    const provider = createProvider(cfg, { resolvePath: (p: string) => p } as any);

    // Should not throw even though PGVector is missing
    const results = await provider.search("test", { user_id: "u1" });
    expect(results).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// 8. OSSProvider: history() error handler
// ---------------------------------------------------------------------------
describe("OSSProvider — history error handling", () => {
  /** When set, the mock history() throws this value instead of an Error. */
  let historyThrowValue: unknown;

  beforeEach(() => {
    historyThrowValue = new Error("history not available");
    vi.resetModules();

    vi.doMock("mem0ai/oss", () => ({
      Memory: class MockMemory {
        constructor() {}
        async search() { return { results: [] }; }
        async get() { return {}; }
        async getAll() { return []; }
        async add() { return { results: [] }; }
        async delete() {}
        async history() { throw historyThrowValue; }
      },
      ...vectorStubs(),
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns empty array and warns when history() throws an Error", async () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: { disableHistory: true },
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    await provider.search("test", { user_id: "u1" });

    const result = await provider.history("mem-123");
    expect(result).toEqual([]);
    expect(warnSpy).toHaveBeenCalledWith(
      "[mem0] OSS history() failed:",
      "history not available",
    );
    warnSpy.mockRestore();
  });

  it("handles non-Error thrown values in history()", async () => {
    historyThrowValue = "raw string error";

    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: { disableHistory: true },
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    await provider.search("test", { user_id: "u1" });

    const result = await provider.history("mem-456");
    expect(result).toEqual([]);
    expect(warnSpy).toHaveBeenCalledWith(
      "[mem0] OSS history() failed:",
      "raw string error",
    );
    warnSpy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// 9. OSSProvider: customInstructions passthrough (v3.0.0: renamed from customPrompt)
// ---------------------------------------------------------------------------
describe("OSSProvider — customInstructions passthrough", () => {
  let capturedConfig: Record<string, unknown> | undefined;

  beforeEach(() => {
    capturedConfig = undefined;
    vi.resetModules();

    vi.doMock("mem0ai/oss", () => ({
      Memory: class MockMemory {
        constructor(config: Record<string, unknown>) {
          capturedConfig = { ...config };
        }
        async search() { return { results: [] }; }
        async get() { return {}; }
        async getAll() { return []; }
        async add() { return { results: [] }; }
        async delete() {}
      },
      ...vectorStubs(),
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // v3.0.0: customPrompt renamed to customInstructions
  it("passes customInstructions to Memory config when provided", async () => {
    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: { disableHistory: true },
      customInstructions: "Extract only user preferences.",
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    await provider.search("test", { user_id: "u1" });

    expect(capturedConfig).toBeDefined();
    expect(capturedConfig!.customInstructions).toBe("Extract only user preferences.");
  });
});
