/**
 * Tests for memory-capability.ts — the MemorySearchManager adapter
 * handed to api.registerMemoryCapability().
 */
import { describe, it, expect, vi } from "vitest";

import { createMemoryCapability } from "../memory-capability.ts";
import { DEFAULT_BASE_URL } from "../cli/config-file.ts";
import type { Mem0Config, Mem0Provider, MemoryItem } from "../types.ts";

function makeConfig(overrides: Partial<Mem0Config> = {}): Mem0Config {
  return {
    mode: "open-source",
    customInstructions: "",
    customCategories: {},
    userId: "user-1",
    autoCapture: false,
    autoRecall: false,
    searchThreshold: 0.1,
    topK: 5,
    ...overrides,
  };
}

function makeMemory(overrides: Partial<MemoryItem> = {}): MemoryItem {
  return {
    id: "mem-001",
    memory: "The user prefers dark mode",
    score: 0.95,
    user_id: "user-1",
    categories: ["preferences"],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeProvider(overrides: Partial<Mem0Provider> = {}): Mem0Provider {
  return {
    add: vi.fn(),
    search: vi.fn().mockResolvedValue([]),
    get: vi.fn().mockResolvedValue(makeMemory()),
    getAll: vi.fn().mockResolvedValue([]),
    update: vi.fn(),
    delete: vi.fn(),
    deleteAll: vi.fn(),
    history: vi.fn().mockResolvedValue([]),
    ...overrides,
  };
}

describe("createMemoryCapability", () => {
  it("registers no publicArtifacts provider", () => {
    expect(
      "publicArtifacts" in
        createMemoryCapability(makeConfig(), makeProvider(), () => "user-1"),
    ).toBe(false);
  });

  describe("runtime.getMemorySearchManager", () => {
    it("returns a real manager implementing the MemorySearchManager contract", async () => {
      const { runtime } = createMemoryCapability(
        makeConfig(),
        makeProvider(),
        () => "user-1",
      );
      const { manager, error } = await runtime.getMemorySearchManager();
      expect(error).toBeUndefined();
      expect(manager).not.toBeNull();
      expect(typeof manager!.search).toBe("function");
      expect(typeof manager!.readFile).toBe("function");
      expect(typeof manager!.status).toBe("function");
      expect(typeof manager!.probeEmbeddingAvailability).toBe("function");
      expect(typeof manager!.probeVectorAvailability).toBe("function");
    });

    it("search() delegates to provider.search and maps results", async () => {
      const memories = [
        makeMemory({ id: "m1", memory: "fact one", score: 0.9 }),
        makeMemory({ id: "m2", memory: "fact two", score: 0.8 }),
      ];
      const provider = makeProvider({
        search: vi.fn().mockResolvedValue(memories),
      });
      const { runtime } = createMemoryCapability(
        makeConfig({ topK: 10, searchThreshold: 0.2 }),
        provider,
        () => "user-1",
      );
      const { manager } = await runtime.getMemorySearchManager();
      const results = await manager!.search("test query", { maxResults: 3 });

      expect(provider.search).toHaveBeenCalledWith("test query", {
        user_id: "user-1",
        top_k: 3,
        threshold: 0.2,
        source: "OPENCLAW",
      });
      expect(results).toHaveLength(2);
      expect(results[0]).toEqual({
        path: "mem0://m1",
        startLine: 0,
        endLine: 0,
        score: 0.9,
        snippet: "fact one",
        source: "memory",
        citation: "preferences",
      });
    });

    it("search() forwards sessionKey to effectiveUserId for per-agent isolation", async () => {
      const provider = makeProvider({
        search: vi.fn().mockResolvedValue([]),
      });
      const effectiveUserId = vi.fn().mockReturnValue("user-1:agent:researcher");
      const { runtime } = createMemoryCapability(
        makeConfig(),
        provider,
        effectiveUserId,
      );
      const { manager } = await runtime.getMemorySearchManager();
      await manager!.search("q", { sessionKey: "agent:researcher:uuid-1" });

      expect(effectiveUserId).toHaveBeenCalledWith("agent:researcher:uuid-1");
      expect(provider.search).toHaveBeenCalledWith("q", expect.objectContaining({
        user_id: "user-1:agent:researcher",
      }));
    });

    it("search() uses config defaults when opts omitted", async () => {
      const provider = makeProvider({
        search: vi.fn().mockResolvedValue([]),
      });
      const { runtime } = createMemoryCapability(
        makeConfig({ topK: 7, searchThreshold: 0.3 }),
        provider,
        () => "user-1",
      );
      const { manager } = await runtime.getMemorySearchManager();
      await manager!.search("q");

      expect(provider.search).toHaveBeenCalledWith("q", {
        user_id: "user-1",
        top_k: 7,
        threshold: 0.3,
        source: "OPENCLAW",
      });
    });

    it("readFile() fetches a memory by ID extracted from the synthetic path", async () => {
      const mem = makeMemory({ id: "abc-123", memory: "the full memory text" });
      const provider = makeProvider({
        get: vi.fn().mockResolvedValue(mem),
      });
      const { runtime } = createMemoryCapability(
        makeConfig(),
        provider,
        () => "user-1",
      );
      const { manager } = await runtime.getMemorySearchManager();
      const result = await manager!.readFile({ relPath: "mem0://abc-123" });

      expect(provider.get).toHaveBeenCalledWith("abc-123");
      expect(result).toEqual({
        text: "the full memory text",
        path: "mem0://abc-123",
      });
    });

    it("readFile() slices multi-line memories with 1-based from/lines", async () => {
      const mem = makeMemory({ id: "ml", memory: "line1\nline2\nline3\nline4" });
      const provider = makeProvider({
        get: vi.fn().mockResolvedValue(mem),
      });
      const { runtime } = createMemoryCapability(
        makeConfig(),
        provider,
        () => "user-1",
      );
      const { manager } = await runtime.getMemorySearchManager();
      const result = await manager!.readFile({ relPath: "mem0://ml", from: 2, lines: 2 });

      expect(result.text).toBe("line2\nline3");
    });

    it("readFile() throws for a deleted or unknown memory", async () => {
      const provider = makeProvider({
        get: vi.fn().mockResolvedValue(null),
      });
      const { runtime } = createMemoryCapability(
        makeConfig(),
        provider,
        () => "user-1",
      );
      const { manager } = await runtime.getMemorySearchManager();

      await expect(
        manager!.readFile({ relPath: "mem0://gone" }),
      ).rejects.toThrow("mem0: memory not found: gone");
    });

    it("readFile() accepts a bare ID without the mem0:// prefix", async () => {
      const provider = makeProvider({
        get: vi.fn().mockResolvedValue(makeMemory({ id: "bare-id" })),
      });
      const { runtime } = createMemoryCapability(
        makeConfig(),
        provider,
        () => "user-1",
      );
      const { manager } = await runtime.getMemorySearchManager();
      await manager!.readFile({ relPath: "bare-id" });

      expect(provider.get).toHaveBeenCalledWith("bare-id");
    });

    it("status() reports mem0 as the provider", async () => {
      const { runtime } = createMemoryCapability(
        makeConfig({ mode: "platform" }),
        makeProvider(),
        () => "user-1",
      );
      const { manager } = await runtime.getMemorySearchManager();
      const s = manager!.status();

      expect(s.backend).toBe("builtin");
      expect(s.provider).toBe("mem0");
      expect(s.custom).toEqual({ mode: "platform", userId: "user-1" });
    });

    it("search() propagates provider errors to the caller", async () => {
      const provider = makeProvider({
        search: vi.fn().mockRejectedValue(new Error("network timeout")),
      });
      const { runtime } = createMemoryCapability(
        makeConfig(),
        provider,
        () => "user-1",
      );
      const { manager } = await runtime.getMemorySearchManager();

      await expect(manager!.search("q")).rejects.toThrow("network timeout");
    });

    it("search() maps missing score to 0 and empty categories to undefined citation", async () => {
      const mem = makeMemory({ id: "x", score: undefined, categories: [] });
      const provider = makeProvider({
        search: vi.fn().mockResolvedValue([mem]),
      });
      const { runtime } = createMemoryCapability(
        makeConfig(),
        provider,
        () => "user-1",
      );
      const { manager } = await runtime.getMemorySearchManager();
      const [result] = await manager!.search("q");

      expect(result.score).toBe(0);
      expect(result.citation).toBeUndefined();
    });

    it("probeEmbeddingAvailability() returns ok", async () => {
      const { runtime } = createMemoryCapability(
        makeConfig(),
        makeProvider(),
        () => "user-1",
      );
      const { manager } = await runtime.getMemorySearchManager();
      await expect(manager!.probeEmbeddingAvailability()).resolves.toEqual({
        ok: true,
      });
    });

    it("probeVectorAvailability() returns true", async () => {
      const { runtime } = createMemoryCapability(
        makeConfig(),
        makeProvider(),
        () => "user-1",
      );
      const { manager } = await runtime.getMemorySearchManager();
      await expect(manager!.probeVectorAvailability()).resolves.toBe(true);
    });
  });

  describe("runtime.resolveMemoryBackendConfig", () => {
    it("returns the configured backend, baseUrl, and userId", () => {
      const { runtime } = createMemoryCapability(
        makeConfig({
          mode: "platform",
          baseUrl: "https://mem0.example.com",
          userId: "u-42",
        }),
        makeProvider(),
        () => "u-42",
      );
      expect(runtime.resolveMemoryBackendConfig()).toEqual({
        backend: "platform",
        baseUrl: "https://mem0.example.com",
        userId: "u-42",
      });
    });

    it("falls back to the default platform baseUrl", () => {
      const { runtime } = createMemoryCapability(
        makeConfig(),
        makeProvider(),
        () => "user-1",
      );
      expect(runtime.resolveMemoryBackendConfig().baseUrl).toBe(
        DEFAULT_BASE_URL,
      );
    });
  });

  it("closeAllMemorySearchManagers resolves", async () => {
    const { runtime } = createMemoryCapability(
      makeConfig(),
      makeProvider(),
      () => "user-1",
    );
    await expect(
      runtime.closeAllMemorySearchManagers(),
    ).resolves.toBeUndefined();
  });
});
