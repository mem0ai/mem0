/**
 * Tests for providers.ts — providerToBackend adapter layer.
 *
 * Verifies that the Backend wrapper correctly delegates to the
 * underlying Mem0Provider methods with proper argument mapping.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import {
  buildQdrantCountRequest,
  countMemories,
  providerToBackend,
} from "../providers.ts";

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

function createOssQdrantConfig() {
  return {
    mode: "open-source" as const,
    userId: DEFAULT_USER,
    topK: 5,
    enableGraph: false,
    autoCapture: true,
    autoRecall: true,
    searchThreshold: 0.5,
    customInstructions: "",
    customCategories: {},
    oss: {
      vectorStore: {
        provider: "qdrant",
        config: {
          host: "127.0.0.1",
          port: 6333,
          collectionName: "openclaw_mem0",
        },
      },
    },
  };
}

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// exact count helpers
// ---------------------------------------------------------------------------

describe("buildQdrantCountRequest", () => {
  it("builds a qdrant count request for OSS mode", () => {
    const request = buildQdrantCountRequest(
      createOssQdrantConfig() as any,
      "test-user:agent:researcher",
    );

    expect(request).not.toBeNull();
    expect(request?.url).toBe(
      "http://127.0.0.1:6333/collections/openclaw_mem0/points/count",
    );
    expect(request?.headers).toEqual({
      "Content-Type": "application/json",
    });
    expect(JSON.parse(request?.body ?? "{}")).toEqual({
      exact: true,
      filter: {
        must: [
          {
            key: "userId",
            match: { value: "test-user:agent:researcher" },
          },
        ],
      },
    });
  });
});

describe("countMemories", () => {
  it("uses qdrant exact count when available", async () => {
    const provider = createMockProvider();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ result: { count: 337 } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const count = await countMemories(provider as any, createOssQdrantConfig() as any, {
      userId: DEFAULT_USER,
      source: "OPENCLAW",
    });

    expect(count).toBe(337);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:6333/collections/openclaw_mem0/points/count",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(provider.getAll).not.toHaveBeenCalled();
  });

  it("falls back to provider.getAll when exact count is unavailable", async () => {
    const provider = createMockProvider();
    provider.getAll.mockResolvedValueOnce([
      { id: "m1", memory: "one" },
      { id: "m2", memory: "two" },
    ]);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    const count = await countMemories(provider as any, createOssQdrantConfig() as any, {
      userId: DEFAULT_USER,
      source: "OPENCLAW",
    });

    expect(count).toBe(2);
    expect(provider.getAll).toHaveBeenCalledWith({
      user_id: DEFAULT_USER,
      source: "OPENCLAW",
    });
  });
});

// ---------------------------------------------------------------------------
// search
// ---------------------------------------------------------------------------

describe("providerToBackend — search", () => {
  it("delegates to provider.search with correct options", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    const results = await backend.search("hello world", {
      topK: 10,
      threshold: 0.5,
      keyword: true,
      rerank: true,
      filters: { category: "preference" },
    });

    expect(provider.search).toHaveBeenCalledWith("hello world", {
      user_id: DEFAULT_USER,
      top_k: 10,
      threshold: 0.5,
      keyword_search: true,
      reranking: true,
      filters: { category: "preference" },
    });
    expect(results).toHaveLength(1);
    expect((results[0] as any).id).toBe("m1");
  });

  it("uses default userId when opts.userId is not provided", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    await backend.search("query");

    expect(provider.search).toHaveBeenCalledWith("query", {
      user_id: DEFAULT_USER,
      top_k: undefined,
      threshold: undefined,
      keyword_search: undefined,
      reranking: undefined,
      filters: undefined,
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

  it("forwards optional add options", async () => {
    const provider = createMockProvider();
    const backend = providerToBackend(provider as any, DEFAULT_USER);

    await backend.add("fact", undefined, {
      runId: "run-1",
      metadata: { source: "test" },
      immutable: true,
      infer: false,
      expires: "2027-01-01",
      enableGraph: true,
    });

    expect(provider.add).toHaveBeenCalledWith(
      [{ role: "user", content: "fact" }],
      expect.objectContaining({
        user_id: DEFAULT_USER,
        run_id: "run-1",
        metadata: { source: "test" },
        immutable: true,
        infer: false,
        expiration_date: "2027-01-01",
        enable_graph: true,
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
