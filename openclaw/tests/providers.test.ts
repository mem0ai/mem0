/**
 * Tests for providers.ts — providerToBackend adapter layer.
 *
 * Verifies that the Backend wrapper correctly delegates to the
 * underlying Mem0Provider methods with proper argument mapping.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

import { providerToBackend } from "../providers.ts";

// ---------------------------------------------------------------------------
// Mock provider factory
// ---------------------------------------------------------------------------

function createMockProvider() {
  return {
    search: vi
      .fn()
      .mockResolvedValue([{ id: "m1", memory: "found", score: 0.9 }]),
    add: vi.fn().mockResolvedValue({
      results: [{ id: "m1", event: "ADD", memory: "stored" }],
    }),
    get: vi
      .fn()
      .mockResolvedValue({ id: "m1", memory: "test", created_at: "2026-01-01" }),
    getAll: vi.fn().mockResolvedValue([{ id: "m1", memory: "listed" }]),
    update: vi.fn().mockResolvedValue(undefined),
    delete: vi.fn().mockResolvedValue(undefined),
    deleteAll: vi.fn().mockResolvedValue(undefined),
    history: vi.fn().mockResolvedValue([]),
  };
}

const DEFAULT_USER = "test-user";

beforeEach(() => {
  vi.resetAllMocks();
});

// ---------------------------------------------------------------------------
// search
// ---------------------------------------------------------------------------

describe("providerToBackend — search", () => {
  // v3.0.0: keyword_search, reranking removed from SDK
  it("delegates to provider.search with correct options", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    const results = await backend.search("hello world", {
      topK: 10,
      threshold: 0.5,
      filters: { category: "preference" },
    });

    expect(provider.search).toHaveBeenCalledWith("hello world", {
      user_id: DEFAULT_USER,
      top_k: 10,
      threshold: 0.5,
      filters: { category: "preference" },
      source: "OPENCLAW",
    });
    expect(results).toHaveLength(1);
    expect((results[0] as any).id).toBe("m1");
  });

  it("uses default userId when opts.userId is not provided", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    await backend.search("query");

    // v3.0.0: keyword_search, reranking removed
    expect(provider.search).toHaveBeenCalledWith("query", {
      user_id: DEFAULT_USER,
      top_k: undefined,
      threshold: undefined,
      filters: undefined,
      source: "OPENCLAW",
    });
  });
});

// ---------------------------------------------------------------------------
// add
// ---------------------------------------------------------------------------

describe("providerToBackend — add", () => {
  it("delegates to provider.add with content as message", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    const result = await backend.add("Remember this fact");

    expect(provider.add).toHaveBeenCalledWith(
      [{ role: "user", content: "Remember this fact" }],
      expect.objectContaining({ user_id: DEFAULT_USER }),
    );
    expect(result).toBeDefined();
  });

  it("passes messages array when provided", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    const messages = [
      { role: "user", content: "Hi" },
      { role: "assistant", content: "Hello" },
    ];
    await backend.add(undefined, messages);

    expect(provider.add).toHaveBeenCalledWith(
      messages,
      expect.objectContaining({ user_id: DEFAULT_USER }),
    );
  });

  // v3.0.0: immutable, expiration_date removed from SDK
  it("forwards optional add options", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    await backend.add("fact", undefined, {
      runId: "run-1",
      metadata: { source: "test" },
      infer: false,
    });

    expect(provider.add).toHaveBeenCalledWith(
      [{ role: "user", content: "fact" }],
      expect.objectContaining({
        user_id: DEFAULT_USER,
        run_id: "run-1",
        metadata: { source: "test" },
        infer: false,
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// get
// ---------------------------------------------------------------------------

describe("providerToBackend — get", () => {
  it("delegates to provider.get", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    const result = await backend.get("mem-123");

    expect(provider.get).toHaveBeenCalledWith("mem-123");
    expect((result as any).id).toBe("m1");
  });
});

// ---------------------------------------------------------------------------
// listMemories
// ---------------------------------------------------------------------------

describe("providerToBackend — listMemories", () => {
  it("delegates to provider.getAll", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    const results = await backend.listMemories({ pageSize: 50 });

    expect(provider.getAll).toHaveBeenCalledWith({
      user_id: DEFAULT_USER,
      page_size: 50,
      source: "OPENCLAW",
    });
    expect(results).toHaveLength(1);
  });

  it("uses default userId when opts.userId is not provided", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    await backend.listMemories();

    expect(provider.getAll).toHaveBeenCalledWith({
      user_id: DEFAULT_USER,
      page_size: undefined,
      source: "OPENCLAW",
    });
  });
});

// ---------------------------------------------------------------------------
// update
// ---------------------------------------------------------------------------

describe("providerToBackend — update", () => {
  it("calls provider.update with content", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    const result = await backend.update("mem-123", "updated text");

    expect(provider.update).toHaveBeenCalledWith("mem-123", "updated text");
    expect((result as any).id).toBe("mem-123");
    expect((result as any).updated).toBe(true);
  });

  it("warns and skips when only metadata is provided (no content)", async () => {
    const provider = createMockProvider();
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    const result = await backend.update("mem-123", undefined, {
      tag: "important",
    });

    expect(provider.update).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("metadata updates are not supported"),
    );
    expect((result as any).id).toBe("mem-123");
    warnSpy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// delete
// ---------------------------------------------------------------------------

describe("providerToBackend — delete", () => {
  it("calls provider.delete with memoryId", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    const result = await backend.delete("mem-456");

    expect(provider.delete).toHaveBeenCalledWith("mem-456");
    expect((result as any).deleted).toBe("mem-456");
  });

  it("calls provider.deleteAll when opts.all is true", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    const result = await backend.delete(undefined, {
      all: true,
      userId: "custom-user",
    });

    expect(provider.deleteAll).toHaveBeenCalledWith("custom-user");
    expect((result as any).deleted).toBe("all");
  });
});

// ---------------------------------------------------------------------------
// deleteEntities (platform-only)
// ---------------------------------------------------------------------------

describe("providerToBackend — deleteEntities", () => {
  it("throws platform-only error", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    await expect(
      backend.deleteEntities({ userId: DEFAULT_USER }),
    ).rejects.toThrow("platform mode");
  });
});

// ---------------------------------------------------------------------------
// status
// ---------------------------------------------------------------------------

describe("providerToBackend — status", () => {
  it("returns connected: true", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    const result = await backend.status();

    expect((result as any).connected).toBe(true);
    expect((result as any).backend).toBe("oss");
  });
});
