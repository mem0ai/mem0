/**
 * Tests for memory-runtime adapter.
 */
import { describe, it, expect, vi } from "vitest";
import { createMemoryRuntime } from "./memory-runtime.ts";
import type { Mem0Provider, Mem0Config } from "./types.ts";
import type { Backend } from "./backend/base.ts";

describe("createMemoryRuntime", () => {
  const mockConfig: Mem0Config = {
    mode: "platform",
    userId: "test-user",
    customInstructions: "",
    customCategories: {},
    autoCapture: false,
    autoRecall: false,
    searchThreshold: 0.5,
    topK: 10,
  };

  const mockBackend: Backend = {
    add: vi.fn(),
    search: vi.fn(),
    get: vi.fn(),
    getAll: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    deleteAll: vi.fn(),
    history: vi.fn(),
  };

  it("returns an object with required methods", () => {
    const mockProvider = {
      add: vi.fn(),
      search: vi.fn(),
      get: vi.fn(),
      getAll: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      deleteAll: vi.fn(),
      history: vi.fn(),
    } as unknown as Mem0Provider;

    const runtime = createMemoryRuntime({
      provider: mockProvider,
      cfg: mockConfig,
      backend: mockBackend,
    });

    expect(runtime).toHaveProperty("getMemorySearchManager");
    expect(runtime).toHaveProperty("resolveMemoryBackendConfig");
    expect(runtime).toHaveProperty("closeAllMemorySearchManagers");
    expect(typeof runtime.getMemorySearchManager).toBe("function");
    expect(typeof runtime.resolveMemoryBackendConfig).toBe("function");
    expect(typeof runtime.closeAllMemorySearchManagers).toBe("function");
  });

  it("returns healthy status when provider.search succeeds", async () => {
    const mockProvider = {
      add: vi.fn(),
      search: vi.fn().mockResolvedValue([]),
      get: vi.fn(),
      getAll: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      deleteAll: vi.fn(),
      history: vi.fn(),
    } as unknown as Mem0Provider;

    const runtime = createMemoryRuntime({
      provider: mockProvider,
      cfg: mockConfig,
      backend: mockBackend,
    });

    const { manager } = await runtime.getMemorySearchManager({});

    const status = await manager.status();

    expect(status).toEqual({ ok: true, embedding: { ok: true } });
  });

  it("returns unhealthy status when provider.search throws", async () => {
    const mockProvider = {
      add: vi.fn(),
      search: vi.fn().mockRejectedValue(new Error("Network error")),
      get: vi.fn(),
      getAll: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      deleteAll: vi.fn(),
      history: vi.fn(),
    } as unknown as Mem0Provider;

    const runtime = createMemoryRuntime({
      provider: mockProvider,
      cfg: mockConfig,
      backend: mockBackend,
    });

    const { manager } = await runtime.getMemorySearchManager({});

    const status = await manager.status();

    expect(status).toEqual({
      ok: false,
      embedding: { ok: false, error: "Error: Network error" },
    });
  });

  it("resolveMemoryBackendConfig returns the injected config", () => {
    const mockProvider = {
      add: vi.fn(),
      search: vi.fn(),
      get: vi.fn(),
      getAll: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      deleteAll: vi.fn(),
      history: vi.fn(),
    } as unknown as Mem0Provider;

    const runtime = createMemoryRuntime({
      provider: mockProvider,
      cfg: mockConfig,
      backend: mockBackend,
    });

    const cfg = runtime.resolveMemoryBackendConfig({});

    expect(cfg).toBe(mockConfig);
    expect(cfg.userId).toBe("test-user");
    expect(cfg.mode).toBe("platform");
  });

  it("manager has probeEmbeddingAvailability and close methods", async () => {
    const mockProvider = {
      add: vi.fn(),
      search: vi.fn().mockResolvedValue([]),
      get: vi.fn(),
      getAll: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      deleteAll: vi.fn(),
      history: vi.fn(),
    } as unknown as Mem0Provider;

    const runtime = createMemoryRuntime({
      provider: mockProvider,
      cfg: mockConfig,
      backend: mockBackend,
    });

    const { manager } = await runtime.getMemorySearchManager({});

    expect(typeof manager.probeEmbeddingAvailability).toBe("function");
    expect(typeof manager.close).toBe("function");

    const availability = await manager.probeEmbeddingAvailability();
    expect(availability).toBe(true);
  });
});