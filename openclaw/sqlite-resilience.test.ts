/**
 * Tests for SQLite resilience fixes:
 * 1. disableHistory config passthrough
 * 2. initPromise poisoning fix (retry after failure)
 * 3. Graceful SQLite fallback in OSSProvider
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { mem0ConfigSchema, createProvider } from "./index.ts";

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

    vi.doMock("mem0ai/oss", () => ({
      Memory: class MockMemory {
        constructor(config: Record<string, unknown>) {
          memoryCallCount++;
          capturedConfig = { ...config };
        }
        async add() { return { results: [] }; }
        async search() { return { results: [] }; }
        async get() { return {}; }
        async getAll() { return []; }
        async delete() { }
      },
    }));
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
    } catch { /* provider may fail on mock, that's ok */ }

    expect(capturedConfig).toBeDefined();
    expect(capturedConfig!.disableHistory).toBe(true);
  });

  it("does not set disableHistory when not configured", async () => {
    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: {},
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    try {
      await provider.search("test", { user_id: "u1" });
    } catch { }

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

    vi.doMock("mem0ai/oss", () => ({
      Memory: class MockMemory {
        constructor() {
          callCount++;
          if (callCount === 1) {
            throw new Error("SQLITE_CANTOPEN: simulated binding failure");
          }
          // Second+ call succeeds
        }
        async search() { return { results: [] }; }
        async get() { return {}; }
        async getAll() { return []; }
        async add() { return { results: [] }; }
        async delete() { }
      },
    }));
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
    await expect(
      provider.search("test", { user_id: "u1" }),
    ).rejects.toThrow("SQLITE_CANTOPEN");

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

  beforeEach(() => {
    capturedConfigs = [];

    vi.doMock("mem0ai/oss", () => ({
      Memory: class MockMemory {
        constructor(config: Record<string, unknown>) {
          capturedConfigs.push({ ...config });
          if (!config.disableHistory) {
            throw new Error("Could not locate the bindings file");
          }
          // Succeeds when disableHistory is true
        }
        async search() { return { results: [] }; }
        async get() { return {}; }
        async getAll() { return []; }
        async add() { return { results: [] }; }
        async delete() { }
      },
    }));
  });

  it("retries with disableHistory: true when initial construction fails", async () => {
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

  it("does not retry when disableHistory is already true", async () => {
    vi.doMock("mem0ai/oss", () => ({
      Memory: class MockMemory {
        constructor(config: Record<string, unknown>) {
          // Fail even with disableHistory (e.g. vector store issue)
          throw new Error("vector store connection refused");
        }
      },
    }));

    const { createProvider } = await import("./index.ts");
    const cfg = mem0ConfigSchema.parse({
      mode: "open-source",
      oss: { disableHistory: true },
    });
    const api = { resolvePath: (p: string) => p } as any;
    const provider = createProvider(cfg, api);

    // Should throw — no fallback possible when disableHistory was already set
    await expect(
      provider.search("test", { user_id: "u1" }),
    ).rejects.toThrow("vector store connection refused");
  });
});

// ---------------------------------------------------------------------------
// 5. PlatformProvider — initPromise retry after failure
// ---------------------------------------------------------------------------
describe("PlatformProvider — initPromise retry after failure", () => {
  let callCount: number;

  beforeEach(() => {
    callCount = 0;

    vi.doMock("mem0ai", () => ({
      default: class MockMemoryClient {
        constructor() {
          callCount++;
          if (callCount === 1) {
            throw new Error("Network timeout");
          }
        }
        async search() { return []; }
        async get() { return {}; }
        async getAll() { return []; }
        async add() { return { results: [] }; }
        async delete() { }
      },
    }));
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
    await expect(
      provider.search("test", { user_id: "u1" }),
    ).rejects.toThrow("Network timeout");

    // Second call should retry (not return cached rejection)
    const results = await provider.search("test", { user_id: "u1" });
    expect(results).toBeDefined();
    expect(callCount).toBe(2);
  });
});
