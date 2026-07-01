/**
 * OSS Memory unit tests — get, update, delete, deleteAll, getAll, search, history.
 * Content-based LLM mock. Tests verify real behavior, not mock echoes.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import type { MemoryItem, SearchResult } from "../src/types";

jest.setTimeout(30000);

// Mock Google modules to prevent @google/genai crash in CI
jest.mock("../src/embeddings/google", () => ({
  GoogleEmbedder: jest.fn(),
}));
jest.mock("../src/llms/google", () => ({
  GoogleLLM: jest.fn(),
}));

jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest
      .fn()
      .mockImplementation(
        (messages: Array<{ role: string; content: string }>) => {
          // V3 pipeline: single LLM call with additive extraction prompt.
          // Extract the user input from the prompt to produce unique memories.
          const userMsg = messages.find((m) => m.role === "user");
          const content = userMsg?.content ?? "";
          // Pull the text between "## New Messages" and the next "##"
          const newMsgMatch = content.match(
            /## New Messages\n([\s\S]*?)(?=\n##|$)/,
          );
          const extracted = newMsgMatch ? newMsgMatch[1].trim() : "stored fact";
          return JSON.stringify({
            memory: [
              {
                id: "0",
                text: extracted,
                attributed_to: "user",
              },
            ],
          });
        },
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
        collectionName: `test-crud-${Date.now()}-${Math.random()}`,
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

// ─── get() ───────────────────────────────────────────────

describe("Memory - get()", () => {
  let memory: Memory;
  const userId = `get_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("returns the memory matching the ID from add()", async () => {
    const addResult: SearchResult = await memory.add("I love AI", {
      userId,
    });
    const id = addResult.results[0].id;
    const item: MemoryItem | null = await memory.get(id);
    expect(item).not.toBeNull();
    expect(item!.id).toBe(id);
  });

  test("returns a string for the memory field", async () => {
    const addResult: SearchResult = await memory.add("Testing get", {
      userId,
    });
    const item: MemoryItem | null = await memory.get(addResult.results[0].id);
    expect(typeof item!.memory).toBe("string");
  });

  test("returns null for non-existent ID", async () => {
    const item = await memory.get("nonexistent-uuid-12345");
    expect(item).toBeNull();
  });

  test("returns hash and createdAt on stored memory", async () => {
    const addResult: SearchResult = await memory.add("Hash test", {
      userId,
    });
    const item: MemoryItem | null = await memory.get(addResult.results[0].id);
    expect(typeof item!.hash).toBe("string");
    expect(item!.createdAt).toBeDefined();
    expect(new Date(item!.createdAt!).toString()).not.toBe("Invalid Date");
  });

  test("normalizes camelCase scope payloads without leaking aliases into metadata", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const getSpy = jest.spyOn(vectorStore, "get").mockResolvedValueOnce({
      id: "redis-shaped-memory",
      payload: {
        data: "redis shaped memory",
        hash: "redis-hash",
        userId: "target-user",
        agentId: "agent-a",
        runId: "run-a",
        source: "redis",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    });

    try {
      const item = await scopedMemory.get("redis-shaped-memory");

      expect(getSpy).toHaveBeenCalledWith("redis-shaped-memory");
      expect(item).toEqual(
        expect.objectContaining({
          id: "redis-shaped-memory",
          memory: "redis shaped memory",
          user_id: "target-user",
          agent_id: "agent-a",
          run_id: "run-a",
        }),
      );
      expect(item!.metadata).toEqual({ source: "redis" });
      expect(item!.metadata).not.toHaveProperty("userId");
      expect(item!.metadata).not.toHaveProperty("agentId");
      expect(item!.metadata).not.toHaveProperty("runId");
    } finally {
      getSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("keeps canonical scope payloads out of metadata", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const getSpy = jest.spyOn(vectorStore, "get").mockResolvedValueOnce({
      id: "canonical-memory",
      payload: {
        data: "canonical memory",
        hash: "canonical-hash",
        user_id: "target-user",
        agent_id: "agent-a",
        run_id: "run-a",
        source: "memory",
        created_at: "2026-01-01T00:00:00.000Z",
        updated_at: "2026-01-02T00:00:00.000Z",
      },
    });

    try {
      const item = await scopedMemory.get("canonical-memory");

      expect(item).toEqual(
        expect.objectContaining({
          id: "canonical-memory",
          memory: "canonical memory",
          user_id: "target-user",
          agent_id: "agent-a",
          run_id: "run-a",
          createdAt: "2026-01-01T00:00:00.000Z",
          updatedAt: "2026-01-02T00:00:00.000Z",
        }),
      );
      expect(item!.metadata).toEqual({ source: "memory" });
      expect(item!.metadata).not.toHaveProperty("user_id");
      expect(item!.metadata).not.toHaveProperty("agent_id");
      expect(item!.metadata).not.toHaveProperty("run_id");
      expect(item!.metadata).not.toHaveProperty("created_at");
      expect(item!.metadata).not.toHaveProperty("updated_at");
    } finally {
      getSpy.mockRestore();
      await scopedMemory.reset();
    }
  });
});

describe("Memory - provider scope filters", () => {
  function providerFiltersFor(
    provider: string,
    filters: Record<string, any>,
  ): Record<string, any> | undefined {
    const memory = Object.create(Memory.prototype) as any;
    memory.config = { vectorStore: { provider } };
    return memory._providerFiltersForRequestedScope(filters);
  }

  function providerFilterVariantsFor(
    provider: string,
    filters: Record<string, any>,
  ): Array<Record<string, any> | undefined> {
    const memory = Object.create(Memory.prototype) as any;
    memory.config = { vectorStore: { provider } };
    return memory._providerFilterVariantsForRequestedScope(filters);
  }

  test("widens qdrant and pgvector scope filters to snake and camel aliases", () => {
    const expected = {
      topic: "preferences",
      $and: [
        {
          $or: [{ user_id: "target-user" }, { userId: "target-user" }],
        },
        {
          $or: [{ agent_id: "agent-a" }, { agentId: "agent-a" }],
        },
      ],
    };

    expect(
      providerFiltersFor("qdrant", {
        user_id: "target-user",
        agent_id: "agent-a",
        topic: "preferences",
      }),
    ).toEqual(expected);
    expect(
      providerFiltersFor("pgvector", {
        user_id: "target-user",
        agent_id: "agent-a",
        topic: "preferences",
      }),
    ).toEqual(expected);
  });

  test("preserves caller OR filters when widening provider scope aliases", () => {
    expect(
      providerFiltersFor("pgvector", {
        user_id: "target-user",
        $or: [{ topic: "travel" }, { topic: "food" }],
      }),
    ).toEqual({
      $or: [{ topic: "travel" }, { topic: "food" }],
      $and: [
        {
          $or: [{ user_id: "target-user" }, { userId: "target-user" }],
        },
      ],
    });
  });

  test("widens nested logical scope filters for alias-aware providers", () => {
    expect(
      providerFiltersFor("qdrant", {
        user_id: "target-user",
        $or: [{ agent_id: "agent-a" }, { topic: "travel" }],
      }),
    ).toEqual({
      $or: [
        { $or: [{ agent_id: "agent-a" }, { agentId: "agent-a" }] },
        { topic: "travel" },
      ],
      $and: [
        {
          $or: [{ user_id: "target-user" }, { userId: "target-user" }],
        },
      ],
    });
  });

  test("fails closed when provider scope alias widening exceeds complexity caps", () => {
    expect(() =>
      providerFiltersFor("qdrant", {
        $and: Array.from({ length: 257 }, () => ({
          user_id: "target-user",
        })),
      }),
    ).toThrow("Scope filter is too complex to safely widen");
  });

  test("keeps nested wildcard scope filters out of provider filters", () => {
    expect(
      providerFiltersFor("memory", {
        user_id: "target-user",
        $or: [{ agent_id: "*" }, { topic: "travel" }],
      }),
    ).toEqual({ user_id: "target-user" });

    expect(
      providerFiltersFor("qdrant", {
        user_id: "target-user",
        $or: [{ agent_id: "*" }, { topic: "travel" }],
      }),
    ).toEqual({
      $or: [{ user_id: "target-user" }, { userId: "target-user" }],
    });
  });

  test("keeps vectorize default provider filters scoped to stored snake_case metadata keys", () => {
    expect(
      providerFiltersFor("vectorize", {
        userId: "target-user",
        agentId: "agent-a",
        topic: "preferences",
      }),
    ).toEqual({
      user_id: "target-user",
      agent_id: "agent-a",
    });

    expect(
      providerFiltersFor("vectorize", {
        user_id: "target-user",
        agent_id: "agent-a",
        topic: "preferences",
      }),
    ).toEqual({
      user_id: "target-user",
      agent_id: "agent-a",
    });
  });

  test("queries both canonical and legacy Vectorize scope indexes", () => {
    expect(
      providerFilterVariantsFor("vectorize", {
        userId: "target-user",
        agentId: "agent-a",
        topic: "preferences",
      }),
    ).toEqual([
      { user_id: "target-user", agent_id: "agent-a" },
      { user_id: "target-user", agentId: "agent-a" },
      { userId: "target-user", agent_id: "agent-a" },
      { userId: "target-user", agentId: "agent-a" },
    ]);

    expect(
      providerFilterVariantsFor("vectorize", {
        AND: [{ user_id: "target-user" }, { topic: "preferences" }],
      }),
    ).toEqual([{ user_id: "target-user" }, { userId: "target-user" }]);
  });

  test("uses the TypeScript Azure AI Search provider name for provider result caps", () => {
    const memory = Object.create(Memory.prototype) as any;
    memory.config = { vectorStore: { provider: "azure-ai-search" } };

    expect(memory._effectiveProviderLimit(10000)).toBe(1000);
    expect(memory._effectiveProviderLimit(60)).toBe(60);
  });

  test("rejects conflicting snake_case and camelCase scope equality filters", () => {
    const memory = Object.create(Memory.prototype) as any;

    expect(() =>
      memory._assertSafeScopeFilters(
        { user_id: "canonical-user", userId: "alias-user" },
        "search",
      ),
    ).toThrow("Conflicting scope filters [user_id]");
  });

  test("strips logical filters for providers without logical filter support", () => {
    expect(
      providerFiltersFor("redis", {
        user_id: "target-user",
        $and: [{ topic: "travel" }, { agent_id: "agent-a" }],
        source: "import",
      }),
    ).toEqual({
      user_id: "target-user",
      agent_id: "agent-a",
    });

    expect(
      providerFiltersFor("azure-ai-search", {
        user_id: "target-user",
        $or: [{ topic: "travel" }, { topic: "food" }],
      }),
    ).toEqual({
      user_id: "target-user",
    });
  });

  test("keeps required nested scope filters for providers without logical support", () => {
    expect(
      providerFiltersFor("redis", {
        AND: [{ userId: "target-user" }, { topic: "travel" }],
        source: "import",
      }),
    ).toEqual({
      user_id: "target-user",
    });

    expect(
      providerFiltersFor("azure-ai-search", {
        OR: [
          { userId: "target-user", topic: "travel" },
          { user_id: "target-user", topic: "food" },
        ],
      }),
    ).toEqual({
      user_id: "target-user",
    });
  });

  test("omits unsupported advanced metadata predicates for providers without logical support", () => {
    expect(
      providerFiltersFor("redis", {
        user_id: "target-user",
        source: "import",
        topic: { contains: "travel" },
        tags: ["personal", "travel"],
        marker: "*",
      }),
    ).toEqual({
      user_id: "target-user",
    });
  });

  test("fails closed when nested alias widening exceeds depth caps", () => {
    const nested = Array.from({ length: 34 }).reduce<Record<string, any>>(
      (acc) => ({ $and: [acc] }),
      { user_id: "target-user" },
    );

    expect(() => providerFiltersFor("qdrant", nested)).toThrow(
      "Scope filter is too complex to safely widen",
    );
  });

  test("passes widened provider scope filters through public getAll calls", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "qdrant";

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "owned-memory",
        payload: {
          data: "target user memory",
          hash: "owned-hash",
          userId: "target-user",
          agentId: "agent-a",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([rows, rows.length]);

    try {
      const result: SearchResult = await scopedMemory.getAll({
        filters: { user_id: "target-user", agent_id: "agent-a" },
        topK: 5,
      });

      expect(listSpy).toHaveBeenCalledWith(
        {
          $and: [
            {
              $or: [{ user_id: "target-user" }, { userId: "target-user" }],
            },
            {
              $or: [{ agent_id: "agent-a" }, { agentId: "agent-a" }],
            },
          ],
        },
        60,
      );
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
    } finally {
      listSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("uses camelCase public read filters with the default memory provider", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "owned-memory",
        payload: {
          data: "target user memory",
          hash: "owned-hash",
          user_id: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([rows, rows.length]);
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        ...rows[0],
        score: 0.99,
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const getAllResult: SearchResult = await scopedMemory.getAll({
        filters: { userId: "  target-user  " },
        topK: 5,
      });
      const searchResult: SearchResult = await scopedMemory.search("target", {
        filters: { userId: "  target-user  " },
        threshold: 0,
        topK: 5,
      });

      expect(listSpy).toHaveBeenCalledWith({ user_id: "target-user" }, 60);
      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        { user_id: "target-user" },
      );
      expect(getAllResult.results.map((item) => item.id)).toEqual([
        "owned-memory",
      ]);
      expect(searchResult.results.map((item) => item.id)).toEqual([
        "owned-memory",
      ]);
    } finally {
      listSpy.mockRestore();
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("normalizes nested camelCase public read scope filters", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "owned-memory",
        payload: {
          data: "target user travel memory",
          hash: "owned-hash",
          user_id: "target-user",
          topic: "travel",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([rows, rows.length]);
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        ...rows[0],
        score: 0.99,
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);
    const filters = {
      AND: [{ userId: "  target-user  " }, { topic: "travel" }],
    };

    try {
      const getAllResult: SearchResult = await scopedMemory.getAll({
        filters,
        topK: 5,
      });
      const searchResult: SearchResult = await scopedMemory.search("target", {
        filters,
        threshold: 0,
        topK: 5,
      });

      expect(listSpy).toHaveBeenCalledWith(
        { AND: [{ user_id: "target-user" }, { topic: "travel" }] },
        60,
      );
      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        { $and: [{ user_id: "target-user" }, { topic: "travel" }] },
      );
      expect(getAllResult.results.map((item) => item.id)).toEqual([
        "owned-memory",
      ]);
      expect(searchResult.results.map((item) => item.id)).toEqual([
        "owned-memory",
      ]);
    } finally {
      listSpy.mockRestore();
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("rejects invalid nested camelCase scope values before provider reads", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const listSpy = jest.spyOn(vectorStore, "list");
    const searchSpy = jest.spyOn(vectorStore, "search");
    const keywordSpy = jest.spyOn(vectorStore, "keywordSearch");
    const filters = { AND: [{ userId: "target user" }] };

    try {
      await expect(
        scopedMemory.getAll({
          filters,
          topK: 5,
        }),
      ).rejects.toThrow("Invalid user_id: cannot contain whitespace");
      await expect(
        scopedMemory.search("target", {
          filters,
          threshold: 0,
          topK: 5,
        }),
      ).rejects.toThrow("Invalid user_id: cannot contain whitespace");

      expect(listSpy).not.toHaveBeenCalled();
      expect(searchSpy).not.toHaveBeenCalled();
      expect(keywordSpy).not.toHaveBeenCalled();
    } finally {
      listSpy.mockRestore();
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });
});

// ─── update() ────────────────────────────────────────────

describe("Memory - update()", () => {
  let memory: Memory;
  const userId = `update_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  // Use infer: false for update tests — bypasses LLM, gives us a stable ID
  test("returns success message", async () => {
    const addResult: SearchResult = await memory.add("Original", {
      userId,
      infer: false,
    });
    const id = addResult.results[0].id;
    const result = await memory.update(id, "Updated");
    expect(result.message).toBe("Memory updated successfully!");
  });

  test("persists the updated text", async () => {
    const addResult: SearchResult = await memory.add("Before update", {
      userId,
      infer: false,
    });
    const id = addResult.results[0].id;
    await memory.update(id, "After update");
    const item: MemoryItem | null = await memory.get(id);
    expect(item!.memory).toBe("After update");
  });

  test("preserves createdAt and sets updatedAt", async () => {
    const addResult: SearchResult = await memory.add("Timestamp test", {
      userId,
      infer: false,
    });
    const id = addResult.results[0].id;
    const before: MemoryItem | null = await memory.get(id);
    const originalCreatedAt = before!.createdAt;

    await memory.update(id, "New text");
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.createdAt).toBe(originalCreatedAt);
    expect(after!.updatedAt).toBeDefined();
  });

  test("updates the hash", async () => {
    const addResult: SearchResult = await memory.add("Hash change", {
      userId,
      infer: false,
    });
    const id = addResult.results[0].id;
    const before: MemoryItem | null = await memory.get(id);
    await memory.update(id, "Completely different text");
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.hash).not.toBe(before!.hash);
  });

  test("preserves custom metadata fields after update", async () => {
    const addResult: SearchResult = await memory.add("Original text", {
      userId,
      metadata: { category: "hobbies", priority: "high" },
      infer: false,
    });
    const id = addResult.results[0].id;
    await memory.update(id, "Updated text");
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.memory).toBe("Updated text");
    expect(after!.metadata).toEqual(
      expect.objectContaining({ category: "hobbies", priority: "high" }),
    );
  });
});

// ─── delete() ────────────────────────────────────────────

describe("Memory - delete()", () => {
  let memory: Memory;
  const userId = `delete_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("returns success message", async () => {
    const addResult: SearchResult = await memory.add("Delete me", {
      userId,
      infer: false,
    });
    const result = await memory.delete(addResult.results[0].id);
    expect(result.message).toBe("Memory deleted successfully!");
  });

  test("get() returns null after deletion", async () => {
    const addResult: SearchResult = await memory.add("Temporary", {
      userId,
      infer: false,
    });
    const id = addResult.results[0].id;
    await memory.delete(id);
    expect(await memory.get(id)).toBeNull();
  });
});

// ─── deleteAll() ─────────────────────────────────────────

describe("Memory - deleteAll()", () => {
  let memory: Memory;
  const userId = `deleteall_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("removes all memories for the user and returns success", async () => {
    await memory.add("Fact A", { userId });
    await memory.add("Fact B", { userId });
    const result = await memory.deleteAll({ userId });
    expect(result.message).toBe("Memories deleted successfully!");
    const remaining: SearchResult = await memory.getAll({
      filters: { user_id: userId },
    });
    expect(remaining.results).toHaveLength(0);
  });

  test("throws when no filter is provided", async () => {
    await expect(memory.deleteAll({} as any)).rejects.toThrow(
      "At least one filter is required to delete all memories",
    );
  });

  test("rejects filters config instead of ignoring it for destructive deletes", async () => {
    await expect(
      memory.deleteAll({
        userId,
        filters: { NOT: { topic: "secret" } },
      } as any),
    ).rejects.toThrow("deleteAll() does not support filters");
  });

  test("rejects logical operator keys for destructive deletes", async () => {
    await expect(
      memory.deleteAll({
        userId,
        NOT: { topic: "secret" },
      } as any),
    ).rejects.toThrow("Logical filters [NOT] are not supported in deleteAll()");
  });
});

// ─── getAll() ────────────────────────────────────────────

describe("Memory - getAll()", () => {
  let memory: Memory;
  const userId = `getall_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("returns all stored memories for the user", async () => {
    await memory.add("First", { userId });
    await memory.add("Second", { userId });
    const result: SearchResult = await memory.getAll({
      filters: { user_id: userId },
    });
    expect(Array.isArray(result.results)).toBe(true);
    expect(result.results.length).toBeGreaterThanOrEqual(2);
  });

  test("each result has id and memory fields", async () => {
    const result: SearchResult = await memory.getAll({
      filters: { user_id: userId },
    });
    for (const item of result.results) {
      expect(item.id).toBeDefined();
      expect(typeof item.memory).toBe("string");
    }
  });

  test("returns empty array when no memories exist", async () => {
    const result: SearchResult = await memory.getAll({
      filters: { user_id: "no_such_user" },
    });
    expect(result.results).toHaveLength(0);
  });

  test("filters polluted vector store list results by requested scope", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "foreign-memory",
        payload: {
          data: "wrong user memory",
          hash: "foreign-hash",
          userId: "other-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        payload: {
          data: "target user memory",
          hash: "owned-hash",
          userId: "target-user",
          agentId: "agent-extra",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([rows, rows.length]);

    try {
      const result: SearchResult = await scopedMemory.getAll({
        filters: { user_id: "target-user" },
        topK: 5,
      });

      expect(listSpy).toHaveBeenCalledWith({ user_id: "target-user" }, 60);
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
      expect(result.results[0].memory).toBe("target user memory");
      expect(result.results[0]).toEqual(
        expect.objectContaining({
          user_id: "target-user",
          agent_id: "agent-extra",
        }),
      );
      expect(result.results[0].metadata).not.toHaveProperty("userId");
      expect(result.results[0].metadata).not.toHaveProperty("agentId");
    } finally {
      listSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test.each([
    ["user_id", { user_id: "*" }],
    ["agent_id", { agent_id: "*" }],
    ["run_id", { run_id: "*" }],
    [
      "agent_id",
      { user_id: "target-user", OR: [{ agent_id: "*" }, { topic: "travel" }] },
    ],
  ])("rejects wildcard %s scope filters for getAll", async (key, filters) => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const listSpy = jest.spyOn(vectorStore, "list");

    try {
      await expect(
        scopedMemory.getAll({
          filters,
          topK: 5,
        }),
      ).rejects.toThrow(
        `Wildcard scope filters [${key}] are not supported in getAll()`,
      );

      expect(listSpy).not.toHaveBeenCalled();
    } finally {
      listSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test.each([
    [
      "array shorthand",
      { user_id: ["target-user", "other-user"] },
      "Scope filter [user_id] in getAll() must use explicit equality",
    ],
    [
      "negative operator",
      { user_id: { ne: "other-user" } },
      "Scope filter [user_id] in getAll() must use explicit equality",
    ],
    [
      "in operator",
      { user_id: { in: ["target-user"] } },
      "Scope filter [user_id] in getAll() must use explicit equality",
    ],
    [
      "nin operator",
      { user_id: { nin: ["other-user"] } },
      "Scope filter [user_id] in getAll() must use explicit equality",
    ],
    [
      "range operator",
      { user_id: { gte: "target-user" } },
      "Scope filter [user_id] in getAll() must use explicit equality",
    ],
    [
      "text operator",
      { user_id: { contains: "target" } },
      "Scope filter [user_id] in getAll() must use explicit equality",
    ],
    [
      "multi-scope OR",
      { OR: [{ user_id: "target-user" }, { user_id: "other-user" }] },
      "filters must contain at least one of: user_id, agent_id, run_id",
    ],
    [
      "negative logical scope",
      { user_id: "target-user", NOT: [{ agent_id: "blocked-agent" }] },
      "Negative scope filters [agent_id] are not supported in getAll()",
    ],
    [
      "malformed AND",
      { user_id: "target-user", AND: { topic: "travel" } } as any,
      "AND operator requires a list of conditions",
    ],
    [
      "malformed OR",
      { user_id: "target-user", OR: { topic: "travel" } } as any,
      "OR operator requires a non-empty list of conditions",
    ],
    [
      "malformed NOT",
      { user_id: "target-user", NOT: { topic: "secret" } } as any,
      "NOT operator requires a non-empty list of conditions",
    ],
  ])(
    "rejects broad %s scope filters for getAll",
    async (_name, filters, message) => {
      const scopedMemory = createMemory();
      await (scopedMemory as any)._ensureInitialized();

      const vectorStore = (scopedMemory as any).vectorStore;
      const listSpy = jest.spyOn(vectorStore, "list");

      try {
        await expect(
          scopedMemory.getAll({
            filters,
            topK: 5,
          }),
        ).rejects.toThrow(message);

        expect(listSpy).not.toHaveBeenCalled();
      } finally {
        listSpy.mockRestore();
        await scopedMemory.reset();
      }
    },
  );

  test("fails closed when cursorless list provider returns a full page before topK is satisfied", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "qdrant";

    const vectorStore = (scopedMemory as any).vectorStore;
    const fullForeignPage = Array.from({ length: 60 }, (_, index) => ({
      id: `foreign-memory-${index}`,
      payload: {
        data: `wrong user memory ${index}`,
        hash: `foreign-hash-${index}`,
        userId: "other-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([fullForeignPage, fullForeignPage.length]);

    try {
      await expect(
        scopedMemory.getAll({
          filters: { user_id: "target-user" },
          topK: 1,
        }),
      ).rejects.toThrow(
        "getAll cannot safely return all requested scoped memories for vector store provider 'qdrant'",
      );

      expect(listSpy).toHaveBeenCalledWith(
        { $or: [{ user_id: "target-user" }, { userId: "target-user" }] },
        60,
      );
    } finally {
      listSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("fails closed when a capped cursorless provider returns its maximum page before topK is satisfied", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "vectorize";

    const vectorStore = (scopedMemory as any).vectorStore;
    const cappedScopedPage = Array.from({ length: 50 }, (_, index) => ({
      id: `owned-memory-${index}`,
      payload: {
        data: `target user memory ${index}`,
        hash: `owned-hash-${index}`,
        user_id: "target-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([cappedScopedPage, cappedScopedPage.length])
      .mockResolvedValueOnce([[], 0]);

    try {
      await expect(
        scopedMemory.getAll({
          filters: { user_id: "target-user" },
          topK: 60,
        }),
      ).rejects.toThrow(
        "getAll cannot safely return all requested scoped memories for vector store provider 'vectorize'",
      );

      expect(listSpy).toHaveBeenNthCalledWith(
        1,
        { user_id: "target-user" },
        50,
      );
      expect(listSpy).toHaveBeenNthCalledWith(2, { userId: "target-user" }, 50);
    } finally {
      listSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("reads Vectorize legacy alias-only rows through scoped getAll", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "vectorize";

    const vectorStore = (scopedMemory as any).vectorStore;
    const canonicalRows = [
      {
        id: "canonical-memory",
        payload: {
          data: "canonical target memory",
          hash: "canonical-hash",
          user_id: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const legacyRows = [
      {
        id: "legacy-memory",
        payload: {
          data: "legacy target memory",
          hash: "legacy-hash",
          userId: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([canonicalRows, canonicalRows.length])
      .mockResolvedValueOnce([legacyRows, legacyRows.length]);

    try {
      const result: SearchResult = await scopedMemory.getAll({
        filters: { user_id: "target-user" },
        topK: 5,
      });

      expect(listSpy).toHaveBeenNthCalledWith(
        1,
        { user_id: "target-user" },
        50,
      );
      expect(listSpy).toHaveBeenNthCalledWith(2, { userId: "target-user" }, 50);
      expect(result.results.map((item) => item.id)).toEqual([
        "canonical-memory",
        "legacy-memory",
      ]);
      expect(result.results[1]).toEqual(
        expect.objectContaining({ user_id: "target-user" }),
      );
      expect(result.results[1].metadata).not.toHaveProperty("userId");
    } finally {
      listSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("returns scoped results from cursorless providers when the page is not full", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "qdrant";

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "owned-memory",
        payload: {
          data: "target user memory",
          hash: "owned-hash",
          userId: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([rows, rows.length]);

    try {
      const result: SearchResult = await scopedMemory.getAll({
        filters: { user_id: "target-user" },
        topK: 5,
      });

      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
      expect(result.results[0]).toEqual(
        expect.objectContaining({ user_id: "target-user" }),
      );
    } finally {
      listSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("does not fail closed when an exact-count provider proves a getAll page is complete", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "pgvector";

    const vectorStore = (scopedMemory as any).vectorStore;
    const fullForeignPage = Array.from({ length: 60 }, (_, index) => ({
      id: `foreign-memory-${index}`,
      payload: {
        data: `wrong user memory ${index}`,
        hash: `foreign-hash-${index}`,
        userId: "other-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([fullForeignPage, fullForeignPage.length]);

    try {
      const result: SearchResult = await scopedMemory.getAll({
        filters: { user_id: "target-user" },
        topK: 1,
      });

      expect(listSpy).toHaveBeenCalledWith(
        { $or: [{ user_id: "target-user" }, { userId: "target-user" }] },
        60,
      );
      expect(result.results).toEqual([]);
    } finally {
      listSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("keeps exact metadata filtering in Memory when simple providers list with stripped filters", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "redis";

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "wrong-topic-memory",
        payload: {
          data: "target user wrong topic",
          hash: "wrong-topic-hash",
          userId: "target-user",
          topic: "food",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "topic-match-memory",
        payload: {
          data: "target user travel memory",
          hash: "topic-match-hash",
          userId: "target-user",
          topic: "travel",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "foreign-topic-match-memory",
        payload: {
          data: "wrong user travel memory",
          hash: "foreign-topic-match-hash",
          userId: "other-user",
          topic: "travel",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([rows, rows.length]);

    try {
      const result: SearchResult = await scopedMemory.getAll({
        filters: { user_id: "target-user", topic: "travel" },
        topK: 5,
      });

      expect(listSpy).toHaveBeenCalledWith({ user_id: "target-user" }, 60);
      expect(result.results.map((item) => item.id)).toEqual([
        "topic-match-memory",
      ]);
    } finally {
      listSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("keeps logical filtering in Memory when simple providers receive stripped filters", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "redis";

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "wrong-topic-memory",
        payload: {
          data: "target user wrong topic",
          hash: "wrong-topic-hash",
          userId: "target-user",
          agentId: "agent-b",
          topic: "food",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "topic-match-memory",
        payload: {
          data: "target user travel memory",
          hash: "topic-match-hash",
          userId: "target-user",
          agentId: "agent-b",
          topic: "travel",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "agent-match-memory",
        payload: {
          data: "target user agent memory",
          hash: "agent-match-hash",
          userId: "target-user",
          agentId: "agent-a",
          topic: "food",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "foreign-topic-match-memory",
        payload: {
          data: "wrong user travel memory",
          hash: "foreign-topic-match-hash",
          userId: "other-user",
          agentId: "agent-a",
          topic: "travel",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([rows, rows.length]);

    try {
      const result: SearchResult = await scopedMemory.getAll({
        filters: {
          user_id: "target-user",
          OR: [{ topic: "travel" }, { agent_id: "agent-a" }],
        },
        topK: 5,
      });

      expect(listSpy).toHaveBeenCalledWith({ user_id: "target-user" }, 60);
      expect(result.results.map((item) => item.id)).toEqual([
        "topic-match-memory",
        "agent-match-memory",
      ]);
    } finally {
      listSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("fails closed when exact-count getAll recovery reaches the scan ceiling", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "redis";

    const vectorStore = (scopedMemory as any).vectorStore;
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockImplementation(async (...args: unknown[]) => {
        const pageSize = typeof args[1] === "number" ? args[1] : 0;
        return [
          Array.from({ length: pageSize }, (_, index) => ({
            id: `foreign-memory-${pageSize}-${index}`,
            payload: {
              data: `wrong user memory ${index}`,
              hash: `foreign-hash-${pageSize}-${index}`,
              userId: "other-user",
              createdAt: "2026-01-01T00:00:00.000Z",
            },
          })),
          10001,
        ];
      });

    try {
      await expect(
        scopedMemory.getAll({
          filters: {
            user_id: "target-user",
            OR: [{ topic: "travel" }, { agent_id: "agent-a" }],
          },
          topK: 1,
        }),
      ).rejects.toThrow("scoped post-filter recovery reached 10000 rows");

      expect(listSpy).toHaveBeenLastCalledWith(
        { user_id: "target-user" },
        10000,
      );
    } finally {
      listSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("caps exact-count getAll first fetches at the scoped recovery ceiling", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "redis";

    const vectorStore = (scopedMemory as any).vectorStore;
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([[], 10001]);

    try {
      await expect(
        scopedMemory.getAll({
          filters: { user_id: "target-user" },
          topK: 1_000_000,
        }),
      ).rejects.toThrow("scoped post-filter recovery reached 10000 rows");

      expect(listSpy).toHaveBeenCalledTimes(1);
      expect(listSpy).toHaveBeenCalledWith({ user_id: "target-user" }, 10000);
    } finally {
      listSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("prefers canonical scope over conflicting camelCase aliases for list results", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "conflicting-memory",
        payload: {
          data: "conflicting user memory",
          hash: "conflicting-hash",
          user_id: "other-user",
          userId: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        payload: {
          data: "target user memory",
          hash: "owned-hash",
          user_id: "target-user",
          userId: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([rows, rows.length]);

    try {
      const result: SearchResult = await scopedMemory.getAll({
        filters: { user_id: "target-user" },
        topK: 5,
      });

      expect(listSpy).toHaveBeenCalledWith({ user_id: "target-user" }, 60);
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
    } finally {
      listSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("refetches when provider count shows scoped list results are incomplete", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const firstPage = [
      {
        id: "foreign-memory",
        payload: {
          data: "wrong user memory",
          hash: "foreign-hash",
          userId: "other-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const secondPage = [
      ...firstPage,
      {
        id: "owned-memory",
        payload: {
          data: "target user memory",
          hash: "owned-hash",
          userId: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([firstPage, 61])
      .mockResolvedValueOnce([secondPage, 61]);

    try {
      const result: SearchResult = await scopedMemory.getAll({
        filters: { user_id: "target-user" },
        topK: 1,
      });

      expect(listSpy).toHaveBeenNthCalledWith(
        1,
        { user_id: "target-user" },
        60,
      );
      expect(listSpy).toHaveBeenNthCalledWith(
        2,
        { user_id: "target-user" },
        61,
      );
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
    } finally {
      listSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("requires every requested scope key when filtering list results", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "wrong-agent-memory",
        payload: {
          data: "same user wrong agent",
          hash: "wrong-agent-hash",
          userId: "target-user",
          agentId: "other-agent",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "wrong-user-memory",
        payload: {
          data: "wrong user same agent",
          hash: "wrong-user-hash",
          userId: "other-user",
          agentId: "agent-a",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        payload: {
          data: "target user and agent",
          hash: "owned-hash",
          userId: "target-user",
          agentId: "agent-a",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([rows, rows.length]);

    try {
      const result: SearchResult = await scopedMemory.getAll({
        filters: { user_id: "target-user", agent_id: "agent-a" },
        topK: 5,
      });

      expect(listSpy).toHaveBeenCalledWith(
        { user_id: "target-user", agent_id: "agent-a" },
        60,
      );
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
      expect(result.results[0]).toEqual(
        expect.objectContaining({
          user_id: "target-user",
          agent_id: "agent-a",
        }),
      );
    } finally {
      listSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("honors nested scope OR filters when filtering list results", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "wrong-agent-memory",
        payload: {
          data: "same user wrong nested agent",
          hash: "wrong-agent-hash",
          userId: "target-user",
          agentId: "agent-c",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "wrong-user-memory",
        payload: {
          data: "wrong user matching nested agent",
          hash: "wrong-user-hash",
          userId: "other-user",
          agentId: "agent-a",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        payload: {
          data: "target user matching nested agent",
          hash: "owned-hash",
          userId: "target-user",
          agentId: "agent-b",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([rows, rows.length]);

    try {
      const result: SearchResult = await scopedMemory.getAll({
        filters: {
          user_id: "target-user",
          OR: [{ agent_id: "agent-a" }, { agent_id: "agent-b" }],
        },
        topK: 5,
      });

      expect(listSpy).toHaveBeenCalledWith(
        {
          user_id: "target-user",
          OR: [{ agent_id: "agent-a" }, { agent_id: "agent-b" }],
        },
        60,
      );
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
      expect(result.results[0]).toEqual(
        expect.objectContaining({
          user_id: "target-user",
          agent_id: "agent-b",
        }),
      );
    } finally {
      listSpy.mockRestore();
      await scopedMemory.reset();
    }
  });
});

// ─── search() ────────────────────────────────────────────

describe("Memory - search()", () => {
  let memory: Memory;
  const userId = `search_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
    await memory.add("I love TypeScript", { userId });
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("returns SearchResult with results array", async () => {
    const result: SearchResult = await memory.search("TypeScript", {
      filters: { user_id: userId },
    });
    expect(Array.isArray(result.results)).toBe(true);
  });

  test("returns results with score field", async () => {
    const result: SearchResult = await memory.search("content", {
      filters: { user_id: userId },
    });
    if (result.results.length > 0) {
      expect(typeof result.results[0].score).toBe("number");
    }
  });

  test("throws when no userId/agentId/runId provided", async () => {
    await expect(memory.search("query", {} as any)).rejects.toThrow(
      "filters must contain at least one of: user_id, agent_id, run_id",
    );
  });

  test("accepts scope supplied by every top-level AND branch", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "owned-memory",
        score: 0.98,
        payload: {
          data: "target user travel memory",
          hash: "owned-hash",
          userId: "target-user",
          topic: "travel",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: {
          AND: [{ user_id: "target-user" }, { topic: "travel" }],
        },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        { $and: [{ user_id: "target-user" }, { topic: "travel" }] },
      );
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("rejects OR filters when any branch lacks scope", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search");

    try {
      await expect(
        scopedMemory.search("target", {
          filters: {
            OR: [{ user_id: "target-user" }, { topic: "travel" }],
          },
          threshold: 0,
          topK: 5,
        }),
      ).rejects.toThrow(
        "filters must contain at least one of: user_id, agent_id, run_id",
      );

      expect(searchSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("returns empty results for user with no memories", async () => {
    const result: SearchResult = await memory.search("query", {
      filters: { user_id: "empty_user" },
    });
    expect(result.results).toHaveLength(0);
  });

  test("filters polluted vector store search results by requested scope", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "foreign-memory",
        score: 0.99,
        payload: {
          data: "wrong user memory",
          hash: "foreign-hash",
          userId: "other-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        score: 0.98,
        payload: {
          data: "target user memory",
          hash: "owned-hash",
          userId: "target-user",
          agentId: "agent-extra",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: { user_id: "target-user" },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        { user_id: "target-user" },
      );
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
      expect(result.results[0].memory).toBe("target user memory");
      expect(result.results[0]).toEqual(
        expect.objectContaining({
          user_id: "target-user",
          agent_id: "agent-extra",
        }),
      );
      expect(result.results[0].metadata).not.toHaveProperty("userId");
      expect(result.results[0].metadata).not.toHaveProperty("agentId");
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("fails closed when search cannot prove scoped completeness from a full page", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const fullForeignPage = Array.from({ length: 60 }, (_, index) => ({
      id: `foreign-memory-${index}`,
      score: 1 - index / 1000,
      payload: {
        data: `wrong user memory ${index}`,
        hash: `foreign-hash-${index}`,
        userId: "other-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));
    const searchSpy = jest
      .spyOn(vectorStore, "search")
      .mockResolvedValueOnce(fullForeignPage);
    const keywordSpy = jest.spyOn(vectorStore, "keywordSearch");

    try {
      await expect(
        scopedMemory.search("target", {
          filters: { user_id: "target-user" },
          threshold: 0,
          topK: 5,
        }),
      ).rejects.toThrow(
        "search cannot safely return all requested scoped memories for vector store provider 'memory'",
      );

      expect(searchSpy).toHaveBeenCalledWith(mockEmbedding, 60, {
        user_id: "target-user",
      });
      expect(keywordSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("fails closed when a capped search provider cannot satisfy requested topK", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "vectorize";

    const vectorStore = (scopedMemory as any).vectorStore;
    const cappedScopedPage = Array.from({ length: 50 }, (_, index) => ({
      id: `owned-memory-${index}`,
      score: 1 - index / 1000,
      payload: {
        data: `target user memory ${index}`,
        hash: `owned-hash-${index}`,
        user_id: "target-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));
    const searchSpy = jest
      .spyOn(vectorStore, "search")
      .mockResolvedValueOnce(cappedScopedPage)
      .mockResolvedValueOnce([]);
    const keywordSpy = jest.spyOn(vectorStore, "keywordSearch");

    try {
      await expect(
        scopedMemory.search("target", {
          filters: { user_id: "target-user" },
          threshold: 0,
          topK: 60,
        }),
      ).rejects.toThrow(
        "search cannot safely return all requested scoped memories for vector store provider 'vectorize'",
      );

      expect(searchSpy).toHaveBeenNthCalledWith(1, mockEmbedding, 50, {
        user_id: "target-user",
      });
      expect(searchSpy).toHaveBeenNthCalledWith(2, mockEmbedding, 50, {
        userId: "target-user",
      });
      expect(keywordSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("searches Vectorize canonical and legacy scope indexes before post-filtering", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "vectorize";

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest
      .spyOn(vectorStore, "search")
      .mockResolvedValueOnce([
        {
          id: "canonical-memory",
          score: 0.8,
          payload: {
            data: "canonical target memory",
            hash: "canonical-hash",
            user_id: "target-user",
            createdAt: "2026-01-01T00:00:00.000Z",
          },
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "legacy-memory",
          score: 0.9,
          payload: {
            data: "legacy target memory",
            hash: "legacy-hash",
            userId: "target-user",
            createdAt: "2026-01-01T00:00:00.000Z",
          },
        },
      ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValue(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: { user_id: "target-user" },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenNthCalledWith(1, mockEmbedding, 50, {
        user_id: "target-user",
      });
      expect(searchSpy).toHaveBeenNthCalledWith(2, mockEmbedding, 50, {
        userId: "target-user",
      });
      expect(result.results.map((item) => item.id)).toEqual([
        "legacy-memory",
        "canonical-memory",
      ]);
      expect(result.results[0]).toEqual(
        expect.objectContaining({ user_id: "target-user" }),
      );
      expect(result.results[0].metadata).not.toHaveProperty("userId");
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("applies the Azure AI Search cap on search fail-closed checks", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "azure-ai-search";

    const vectorStore = (scopedMemory as any).vectorStore;
    const cappedScopedPage = Array.from({ length: 1000 }, (_, index) => ({
      id: `azure-owned-memory-${index}`,
      score: 1 - index / 10000,
      payload: {
        data: `target user memory ${index}`,
        hash: `azure-owned-hash-${index}`,
        user_id: "target-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));
    const searchSpy = jest
      .spyOn(vectorStore, "search")
      .mockResolvedValueOnce(cappedScopedPage);
    const keywordSpy = jest.spyOn(vectorStore, "keywordSearch");

    try {
      await expect(
        scopedMemory.search("target", {
          filters: { user_id: "target-user" },
          threshold: 0,
          topK: 1001,
        }),
      ).rejects.toThrow(
        "search cannot safely return all requested scoped memories for vector store provider 'azure-ai-search'",
      );

      expect(searchSpy).toHaveBeenCalledWith(mockEmbedding, 1000, {
        user_id: "target-user",
      });
      expect(keywordSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("ignores wrong-scope keyword results when scoring", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "owned-memory",
        score: 0.8,
        payload: {
          data: "target keyword memory",
          hash: "owned-hash",
          user_id: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce([
        {
          id: "foreign-keyword-memory",
          score: 100,
          payload: {
            data: "wrong user keyword memory",
            hash: "foreign-keyword-hash",
            user_id: "other-user",
            createdAt: "2026-01-01T00:00:00.000Z",
          },
        },
      ]);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: { user_id: "target-user" },
        threshold: 0,
        topK: 5,
        explain: true,
      });

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        { user_id: "target-user" },
      );
      expect(keywordSpy).toHaveBeenCalledWith("target", expect.any(Number), {
        user_id: "target-user",
      });
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
      expect((result.results[0] as any).score_details).toEqual(
        expect.objectContaining({
          bm25Score: 0,
          maxPossibleScore: 1,
        }),
      );
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("keeps exact metadata filtering in Memory when simple providers search with stripped filters", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "redis";

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "wrong-topic-memory",
        score: 0.99,
        payload: {
          data: "target user wrong topic",
          hash: "wrong-topic-hash",
          userId: "target-user",
          topic: "food",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "topic-match-memory",
        score: 0.98,
        payload: {
          data: "target user travel memory",
          hash: "topic-match-hash",
          userId: "target-user",
          topic: "travel",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "foreign-topic-match-memory",
        score: 0.97,
        payload: {
          data: "wrong user travel memory",
          hash: "foreign-topic-match-hash",
          userId: "other-user",
          topic: "travel",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const searchSpy = jest
      .spyOn(vectorStore, "search")
      .mockResolvedValueOnce(rows);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: { user_id: "target-user", topic: "travel" },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(mockEmbedding, 60, {
        user_id: "target-user",
      });
      expect(result.results.map((item) => item.id)).toEqual([
        "topic-match-memory",
      ]);
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("keeps logical metadata filtering in Memory when simple providers search with stripped filters", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "redis";

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "wrong-topic-memory",
        score: 0.99,
        payload: {
          data: "target user wrong topic",
          hash: "wrong-topic-hash",
          userId: "target-user",
          agentId: "agent-b",
          topic: "food",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "topic-match-memory",
        score: 0.98,
        payload: {
          data: "target user travel memory",
          hash: "topic-match-hash",
          userId: "target-user",
          agentId: "agent-b",
          topic: "travel",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "agent-match-memory",
        score: 0.97,
        payload: {
          data: "target user agent memory",
          hash: "agent-match-hash",
          userId: "target-user",
          agentId: "agent-a",
          topic: "food",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "foreign-topic-match-memory",
        score: 0.96,
        payload: {
          data: "wrong user travel memory",
          hash: "foreign-topic-match-hash",
          userId: "other-user",
          agentId: "agent-a",
          topic: "travel",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const searchSpy = jest
      .spyOn(vectorStore, "search")
      .mockResolvedValueOnce(rows);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: {
          user_id: "target-user",
          OR: [{ topic: "travel" }, { agent_id: "agent-a" }],
        },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(mockEmbedding, 60, {
        user_id: "target-user",
      });
      expect(result.results.map((item) => item.id)).toEqual([
        "topic-match-memory",
        "agent-match-memory",
      ]);
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("keeps advanced metadata filtering in Memory when simple providers receive exact filters", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "redis";

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "wrong-topic-memory",
        score: 0.99,
        payload: {
          data: "target user wrong topic",
          hash: "wrong-topic-hash",
          userId: "target-user",
          topic: "food",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "topic-match-memory",
        score: 0.98,
        payload: {
          data: "target user travel memory",
          hash: "topic-match-hash",
          userId: "target-user",
          topic: "travel plans",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const searchSpy = jest
      .spyOn(vectorStore, "search")
      .mockResolvedValueOnce(rows);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: {
          user_id: "target-user",
          topic: { contains: "travel" },
        },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(mockEmbedding, 60, {
        user_id: "target-user",
      });
      expect(result.results.map((item) => item.id)).toEqual([
        "topic-match-memory",
      ]);
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("fails closed when keyword search cannot prove scoped completeness from a full page", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "owned-memory",
        score: 0.8,
        payload: {
          data: "target keyword memory",
          hash: "owned-hash",
          user_id: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const fullForeignKeywordPage = Array.from({ length: 60 }, (_, index) => ({
      id: `foreign-keyword-memory-${index}`,
      score: 100 - index,
      payload: {
        data: `wrong user keyword memory ${index}`,
        hash: `foreign-keyword-hash-${index}`,
        user_id: "other-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(fullForeignKeywordPage);

    try {
      await expect(
        scopedMemory.search("target", {
          filters: { user_id: "target-user" },
          threshold: 0,
          topK: 5,
        }),
      ).rejects.toThrow(
        "search cannot safely return all requested scoped memories for vector store provider 'memory'",
      );

      expect(searchSpy).toHaveBeenCalled();
      expect(keywordSpy).toHaveBeenCalledWith("target", 60, {
        user_id: "target-user",
      });
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("requires every requested scope key when filtering search results", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "wrong-agent-memory",
        score: 0.99,
        payload: {
          data: "same user wrong agent",
          hash: "wrong-agent-hash",
          userId: "target-user",
          agentId: "other-agent",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "wrong-user-memory",
        score: 0.98,
        payload: {
          data: "wrong user same agent",
          hash: "wrong-user-hash",
          userId: "other-user",
          agentId: "agent-a",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        score: 0.97,
        payload: {
          data: "target user and agent",
          hash: "owned-hash",
          userId: "target-user",
          agentId: "agent-a",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: { user_id: "target-user", agent_id: "agent-a" },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        { user_id: "target-user", agent_id: "agent-a" },
      );
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
      expect(result.results[0]).toEqual(
        expect.objectContaining({
          user_id: "target-user",
          agent_id: "agent-a",
        }),
      );
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("honors nested scope OR filters when filtering search results", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "wrong-agent-memory",
        score: 0.99,
        payload: {
          data: "same user wrong nested agent",
          hash: "wrong-agent-hash",
          userId: "target-user",
          agentId: "agent-c",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        score: 0.98,
        payload: {
          data: "target user matching nested agent",
          hash: "owned-hash",
          userId: "target-user",
          agentId: "agent-b",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: {
          user_id: "target-user",
          OR: [{ agent_id: "agent-a" }, { agent_id: "agent-b" }],
        },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        {
          user_id: "target-user",
          $or: [{ agent_id: "agent-a" }, { agent_id: "agent-b" }],
        },
      );
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
      expect(result.results[0]).toEqual(
        expect.objectContaining({
          user_id: "target-user",
          agent_id: "agent-b",
        }),
      );
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("honors nested scope AND filters when filtering search results", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "wrong-agent-memory",
        score: 0.99,
        payload: {
          data: "same user wrong nested agent",
          hash: "wrong-agent-hash",
          userId: "target-user",
          agentId: "agent-c",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        score: 0.98,
        payload: {
          data: "target user matching nested agent",
          hash: "owned-hash",
          userId: "target-user",
          agentId: "agent-a",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: {
          user_id: "target-user",
          AND: [{ agent_id: "agent-a" }],
        },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        { user_id: "target-user", $and: [{ agent_id: "agent-a" }] },
      );
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
      expect(result.results[0]).toEqual(
        expect.objectContaining({
          user_id: "target-user",
          agent_id: "agent-a",
        }),
      );
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("honors nested metadata NOT filters when filtering scoped search results", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "blocked-agent-memory",
        score: 0.99,
        payload: {
          data: "blocked nested agent",
          hash: "blocked-agent-hash",
          userId: "target-user",
          agentId: "blocked-agent",
          topic: "blocked",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        score: 0.98,
        payload: {
          data: "allowed nested agent",
          hash: "owned-hash",
          userId: "target-user",
          agentId: "allowed-agent",
          topic: "allowed",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: {
          user_id: "target-user",
          NOT: [{ topic: "blocked" }],
        },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        { user_id: "target-user", $not: [{ topic: "blocked" }] },
      );
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
      expect(result.results[0]).toEqual(
        expect.objectContaining({
          user_id: "target-user",
          agent_id: "allowed-agent",
        }),
      );
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("preserves mixed scope and metadata OR semantics in post-filtering", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "wrong-topic-memory",
        score: 0.99,
        payload: {
          data: "matching scope wrong topic",
          hash: "wrong-topic-hash",
          userId: "target-user",
          agentId: "agent-a",
          topic: "food",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        score: 0.98,
        payload: {
          data: "matching scope and topic",
          hash: "owned-hash",
          userId: "target-user",
          agentId: "agent-a",
          topic: "travel",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: {
          user_id: "target-user",
          OR: [{ agent_id: "agent-a", topic: "travel" }],
        },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        {
          user_id: "target-user",
          $or: [{ agent_id: "agent-a", topic: "travel" }],
        },
      );
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("preserves nested logical scope comparisons in post-filtering", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "low-priority-memory",
        score: 0.99,
        payload: {
          data: "matching scope below priority threshold",
          hash: "low-priority-hash",
          userId: "target-user",
          agentId: "agent-a",
          priority: 5,
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "priority-memory",
        score: 0.98,
        payload: {
          data: "matching priority threshold",
          hash: "priority-hash",
          userId: "target-user",
          agentId: "agent-a",
          priority: "12",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "blocked-topic-memory",
        score: 0.97,
        payload: {
          data: "matching agent blocked by nested NOT",
          hash: "blocked-topic-hash",
          userId: "target-user",
          agentId: "agent-b",
          topic: "secret",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "allowed-topic-memory",
        score: 0.96,
        payload: {
          data: "matching agent allowed by nested NOT",
          hash: "allowed-topic-hash",
          userId: "target-user",
          agentId: "agent-b",
          topic: "public",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: {
          user_id: "target-user",
          OR: [
            { AND: [{ agent_id: "agent-a" }, { priority: { gte: 10 } }] },
            {
              AND: [{ agent_id: "agent-b" }, { NOT: [{ topic: "secret" }] }],
            },
          ],
        },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        {
          user_id: "target-user",
          $or: [
            {
              $and: [{ agent_id: "agent-a" }, { priority: { gte: 10 } }],
            },
            {
              $and: [{ agent_id: "agent-b" }, { $not: [{ topic: "secret" }] }],
            },
          ],
        },
      );
      expect(result.results.map((item) => item.id)).toEqual([
        "priority-memory",
        "allowed-topic-memory",
      ]);
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("rejects conflicting top-level and AND scope filters before searching", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search");
    const keywordSpy = jest.spyOn(vectorStore, "keywordSearch");

    try {
      await expect(
        scopedMemory.search("target", {
          filters: {
            user_id: "trusted-user",
            AND: [{ user_id: "other-user" }],
          },
          threshold: 0,
          topK: 5,
        }),
      ).rejects.toThrow("Conflicting scope filters [user_id]");

      expect(searchSpy).not.toHaveBeenCalled();
      expect(keywordSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("preserves same-field range conjuncts in post-filtering", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "before-range-memory",
        score: 0.99,
        payload: {
          data: "target before range",
          hash: "before-range-hash",
          userId: "target-user",
          createdAt: "2024-12-31T00:00:00.000Z",
        },
      },
      {
        id: "in-range-memory",
        score: 0.98,
        payload: {
          data: "target in range",
          hash: "in-range-hash",
          userId: "target-user",
          createdAt: "2025-03-15T00:00:00.000Z",
        },
      },
      {
        id: "after-range-memory",
        score: 0.97,
        payload: {
          data: "target after range",
          hash: "after-range-hash",
          userId: "target-user",
          createdAt: "2025-12-01T00:00:00.000Z",
        },
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: {
          user_id: "target-user",
          AND: [
            { createdAt: { gte: "2025-01-01T00:00:00.000Z" } },
            { createdAt: { lte: "2025-06-30T23:59:59.999Z" } },
          ],
        },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        {
          user_id: "target-user",
          $and: [
            { createdAt: { gte: "2025-01-01T00:00:00.000Z" } },
            { createdAt: { lte: "2025-06-30T23:59:59.999Z" } },
          ],
        },
      );
      expect(result.results.map((item) => item.id)).toEqual([
        "in-range-memory",
      ]);
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("requires metadata presence for wildcard and negative operators during post-filtering", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "missing-topic-memory",
        score: 0.99,
        payload: {
          data: "target missing topic",
          hash: "missing-topic-hash",
          userId: "target-user",
          status: "active",
          category: "allowed",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "missing-status-memory",
        score: 0.98,
        payload: {
          data: "target missing status",
          hash: "missing-status-hash",
          userId: "target-user",
          topic: "travel",
          category: "allowed",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "missing-category-memory",
        score: 0.97,
        payload: {
          data: "target missing category",
          hash: "missing-category-hash",
          userId: "target-user",
          topic: "travel",
          status: "active",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        score: 0.96,
        payload: {
          data: "target complete metadata",
          hash: "owned-hash",
          userId: "target-user",
          topic: "travel",
          status: "active",
          category: "allowed",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: {
          user_id: "target-user",
          topic: "*",
          status: { ne: "archived" },
          category: { nin: ["blocked"] },
        },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalled();
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("preserves scoped metadata NOT semantics in post-filtering", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "blocked-secret-memory",
        score: 0.99,
        payload: {
          data: "blocked agent secret topic",
          hash: "blocked-secret-hash",
          userId: "target-user",
          agentId: "blocked-agent",
          topic: "secret",
          visibility: "private",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "blocked-public-memory",
        score: 0.98,
        payload: {
          data: "blocked agent public topic",
          hash: "blocked-public-hash",
          userId: "target-user",
          agentId: "blocked-agent",
          topic: "public",
          visibility: "public",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        score: 0.97,
        payload: {
          data: "allowed agent secret topic",
          hash: "owned-hash",
          userId: "target-user",
          agentId: "allowed-agent",
          topic: "secret",
          visibility: "public",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: {
          user_id: "target-user",
          NOT: [{ topic: "secret", visibility: "private" }],
        },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        {
          user_id: "target-user",
          $not: [{ topic: "secret", visibility: "private" }],
        },
      );
      expect(result.results.map((item) => item.id)).toEqual([
        "blocked-public-memory",
        "owned-memory",
      ]);
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test.each([
    ["user_id", { user_id: "*" }],
    ["agent_id", { agent_id: "*" }],
    ["run_id", { run_id: "*" }],
    [
      "agent_id",
      { user_id: "target-user", OR: [{ agent_id: "*" }, { topic: "travel" }] },
    ],
  ])("rejects wildcard %s scope filters for search", async (key, filters) => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search");
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      await expect(
        scopedMemory.search("target", {
          filters,
          threshold: 0,
          topK: 5,
        }),
      ).rejects.toThrow(
        `Wildcard scope filters [${key}] are not supported in search()`,
      );

      expect(searchSpy).not.toHaveBeenCalled();
      expect(keywordSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test.each([
    [
      "array shorthand",
      { user_id: ["target-user", "other-user"] },
      "Scope filter [user_id] in search() must use explicit equality",
    ],
    [
      "negative operator",
      { user_id: { ne: "other-user" } },
      "Scope filter [user_id] in search() must use explicit equality",
    ],
    [
      "in operator",
      { user_id: { in: ["target-user"] } },
      "Scope filter [user_id] in search() must use explicit equality",
    ],
    [
      "nin operator",
      { user_id: { nin: ["other-user"] } },
      "Scope filter [user_id] in search() must use explicit equality",
    ],
    [
      "range operator",
      { user_id: { gte: "target-user" } },
      "Scope filter [user_id] in search() must use explicit equality",
    ],
    [
      "text operator",
      { user_id: { contains: "target" } },
      "Scope filter [user_id] in search() must use explicit equality",
    ],
    [
      "multi-scope OR",
      { OR: [{ user_id: "target-user" }, { user_id: "other-user" }] },
      "filters must contain at least one of: user_id, agent_id, run_id",
    ],
    [
      "negative logical scope",
      { user_id: "target-user", NOT: [{ agent_id: "blocked-agent" }] },
      "Negative scope filters [agent_id] are not supported in search()",
    ],
    [
      "malformed AND",
      { user_id: "target-user", AND: { topic: "travel" } } as any,
      "AND operator requires a list of conditions",
    ],
    [
      "malformed OR",
      { user_id: "target-user", OR: { topic: "travel" } } as any,
      "OR operator requires a non-empty list of conditions",
    ],
    [
      "malformed NOT",
      { user_id: "target-user", NOT: { topic: "secret" } } as any,
      "NOT operator requires a non-empty list of conditions",
    ],
  ])(
    "rejects broad %s scope filters for search",
    async (_name, filters, message) => {
      const scopedMemory = createMemory();
      await (scopedMemory as any)._ensureInitialized();

      const vectorStore = (scopedMemory as any).vectorStore;
      const searchSpy = jest.spyOn(vectorStore, "search");
      const keywordSpy = jest.spyOn(vectorStore, "keywordSearch");

      try {
        await expect(
          scopedMemory.search("target", {
            filters: filters as any,
            threshold: 0,
            topK: 5,
          }),
        ).rejects.toThrow(message);

        expect(searchSpy).not.toHaveBeenCalled();
        expect(keywordSpy).not.toHaveBeenCalled();
      } finally {
        searchSpy.mockRestore();
        keywordSpy.mockRestore();
        await scopedMemory.reset();
      }
    },
  );

  test("prefers canonical scope over conflicting camelCase aliases for search results", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "conflicting-memory",
        score: 0.99,
        payload: {
          data: "conflicting user memory",
          hash: "conflicting-hash",
          user_id: "other-user",
          userId: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        score: 0.98,
        payload: {
          data: "target user memory",
          hash: "owned-hash",
          user_id: "target-user",
          userId: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const keywordSpy = jest
      .spyOn(vectorStore, "keywordSearch")
      .mockResolvedValueOnce(null);

    try {
      const result: SearchResult = await scopedMemory.search("target", {
        filters: { user_id: "target-user" },
        threshold: 0,
        topK: 5,
      });

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        expect.any(Number),
        { user_id: "target-user" },
      );
      expect(result.results.map((item) => item.id)).toEqual(["owned-memory"]);
    } finally {
      searchSpy.mockRestore();
      keywordSpy.mockRestore();
      await scopedMemory.reset();
    }
  });
});

describe("Memory - deleteAll() scope hardening", () => {
  test("does not delete rows outside the requested scope when vector store list is polluted", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "foreign-memory",
        payload: {
          data: "wrong user memory",
          hash: "foreign-hash",
          userId: "other-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        payload: {
          data: "target user memory",
          hash: "owned-hash",
          userId: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];

    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([rows, rows.length]);
    const getSpy = jest
      .spyOn(vectorStore, "get")
      .mockImplementation(async (...args: unknown[]) => {
        const id = String(args[0]);
        const row = rows.find((item) => item.id === id);
        return row ?? null;
      });
    const deleteSpy = jest
      .spyOn(vectorStore, "delete")
      .mockResolvedValue(undefined);
    const entityCleanupSpy = jest
      .spyOn(scopedMemory as any, "_removeMemoryFromEntityStore")
      .mockResolvedValue(undefined);

    try {
      const result = await scopedMemory.deleteAll({ userId: "target-user" });

      expect(result.message).toBe("Memories deleted successfully!");
      expect(listSpy).toHaveBeenCalledWith({ user_id: "target-user" }, 10000);
      expect(deleteSpy).toHaveBeenCalledTimes(1);
      expect(deleteSpy).toHaveBeenCalledWith("owned-memory");
      expect(entityCleanupSpy).toHaveBeenCalledWith("owned-memory", {
        user_id: "target-user",
      });
    } finally {
      listSpy.mockRestore();
      getSpy.mockRestore();
      deleteSpy.mockRestore();
      entityCleanupSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test.each([
    ["user_id", { userId: "*" }],
    ["agent_id", { agentId: "*" }],
    ["run_id", { runId: "*" }],
  ])(
    "rejects wildcard %s filters for destructive bulk deletes",
    async (key, config) => {
      const scopedMemory = createMemory();
      await (scopedMemory as any)._ensureInitialized();

      const vectorStore = (scopedMemory as any).vectorStore;
      const listSpy = jest.spyOn(vectorStore, "list");
      const deleteSpy = jest
        .spyOn(vectorStore, "delete")
        .mockResolvedValue(undefined);
      const entityCleanupSpy = jest
        .spyOn(scopedMemory as any, "_removeMemoryFromEntityStore")
        .mockResolvedValue(undefined);

      try {
        await expect(scopedMemory.deleteAll(config)).rejects.toThrow(
          `Wildcard scope filters [${key}] are not supported in deleteAll()`,
        );

        expect(listSpy).not.toHaveBeenCalled();
        expect(deleteSpy).not.toHaveBeenCalled();
        expect(entityCleanupSpy).not.toHaveBeenCalled();
      } finally {
        listSpy.mockRestore();
        deleteSpy.mockRestore();
        entityCleanupSpy.mockRestore();
        await scopedMemory.reset();
      }
    },
  );

  test("prefers canonical scope over conflicting camelCase aliases before deleting", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "conflicting-memory",
        payload: {
          data: "conflicting user memory",
          hash: "conflicting-hash",
          user_id: "other-user",
          userId: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        payload: {
          data: "target user memory",
          hash: "owned-hash",
          user_id: "target-user",
          userId: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];

    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([rows, rows.length]);
    const getSpy = jest
      .spyOn(vectorStore, "get")
      .mockImplementation(async (...args: unknown[]) => {
        const id = String(args[0]);
        const row = rows.find((item) => item.id === id);
        return row ?? null;
      });
    const deleteSpy = jest
      .spyOn(vectorStore, "delete")
      .mockResolvedValue(undefined);
    const entityCleanupSpy = jest
      .spyOn(scopedMemory as any, "_removeMemoryFromEntityStore")
      .mockResolvedValue(undefined);

    try {
      const result = await scopedMemory.deleteAll({ userId: "target-user" });

      expect(result.message).toBe("Memories deleted successfully!");
      expect(listSpy).toHaveBeenCalledWith({ user_id: "target-user" }, 10000);
      expect(deleteSpy).toHaveBeenCalledTimes(1);
      expect(deleteSpy).toHaveBeenCalledWith("owned-memory");
      expect(entityCleanupSpy).toHaveBeenCalledWith("owned-memory", {
        user_id: "target-user",
      });
    } finally {
      listSpy.mockRestore();
      getSpy.mockRestore();
      deleteSpy.mockRestore();
      entityCleanupSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("fails closed before deleting when exact-count providers report hidden rows", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const firstPage = Array.from({ length: 10000 }, (_, index) => ({
      id: index === 9999 ? "owned-memory" : `foreign-memory-${index}`,
      payload: {
        data:
          index === 9999 ? "target user memory" : `wrong user memory ${index}`,
        hash: index === 9999 ? "owned-hash" : `foreign-hash-${index}`,
        userId: index === 9999 ? "target-user" : "other-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([firstPage, 10001]);
    const deleteSpy = jest
      .spyOn(vectorStore, "delete")
      .mockResolvedValue(undefined);
    const entityCleanupSpy = jest
      .spyOn(scopedMemory as any, "_removeMemoryFromEntityStore")
      .mockResolvedValue(undefined);

    try {
      await expect(
        scopedMemory.deleteAll({ userId: "target-user" }),
      ).rejects.toThrow(
        "scoped rows may be hidden behind an incomplete provider page",
      );

      expect(listSpy).toHaveBeenCalledTimes(1);
      expect(listSpy).toHaveBeenCalledWith({ user_id: "target-user" }, 10000);
      expect(deleteSpy).not.toHaveBeenCalled();
      expect(entityCleanupSpy).not.toHaveBeenCalled();
    } finally {
      listSpy.mockRestore();
      deleteSpy.mockRestore();
      entityCleanupSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("fails closed when scoped rows may be hidden behind a full provider page", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const fullForeignPage = Array.from({ length: 10000 }, (_, index) => ({
      id: `foreign-memory-${index}`,
      payload: {
        data: `wrong user memory ${index}`,
        hash: `foreign-hash-${index}`,
        userId: "other-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));

    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([fullForeignPage, 10001]);
    const deleteSpy = jest
      .spyOn(vectorStore, "delete")
      .mockResolvedValue(undefined);
    const entityCleanupSpy = jest
      .spyOn(scopedMemory as any, "_removeMemoryFromEntityStore")
      .mockResolvedValue(undefined);

    try {
      await expect(
        scopedMemory.deleteAll({ userId: "target-user" }),
      ).rejects.toThrow(
        "scoped rows may be hidden behind an incomplete provider page",
      );

      expect(listSpy).toHaveBeenCalledWith({ user_id: "target-user" }, 10000);
      expect(deleteSpy).not.toHaveBeenCalled();
      expect(entityCleanupSpy).not.toHaveBeenCalled();
    } finally {
      listSpy.mockRestore();
      deleteSpy.mockRestore();
      entityCleanupSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("does not fail closed when an exact-count provider proves a full page is complete", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "pgvector";

    const vectorStore = (scopedMemory as any).vectorStore;
    const fullForeignPage = Array.from({ length: 10000 }, (_, index) => ({
      id: `foreign-memory-${index}`,
      payload: {
        data: `wrong user memory ${index}`,
        hash: `foreign-hash-${index}`,
        userId: "other-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));

    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([fullForeignPage, fullForeignPage.length]);
    const deleteSpy = jest
      .spyOn(vectorStore, "delete")
      .mockResolvedValue(undefined);
    const entityCleanupSpy = jest
      .spyOn(scopedMemory as any, "_removeMemoryFromEntityStore")
      .mockResolvedValue(undefined);

    try {
      const result = await scopedMemory.deleteAll({ userId: "target-user" });

      expect(result.message).toBe("Memories deleted successfully!");
      expect(listSpy).toHaveBeenCalledWith(
        { $or: [{ user_id: "target-user" }, { userId: "target-user" }] },
        10000,
      );
      expect(deleteSpy).not.toHaveBeenCalled();
      expect(entityCleanupSpy).not.toHaveBeenCalled();
    } finally {
      listSpy.mockRestore();
      deleteSpy.mockRestore();
      entityCleanupSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("requires every requested scope key before bulk deleting", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "wrong-agent-memory",
        payload: {
          data: "same user wrong agent",
          hash: "wrong-agent-hash",
          userId: "target-user",
          agentId: "other-agent",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "wrong-user-memory",
        payload: {
          data: "wrong user same agent",
          hash: "wrong-user-hash",
          userId: "other-user",
          agentId: "agent-a",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "owned-memory",
        payload: {
          data: "target user and agent",
          hash: "owned-hash",
          userId: "target-user",
          agentId: "agent-a",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];

    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([rows, rows.length]);
    const getSpy = jest
      .spyOn(vectorStore, "get")
      .mockImplementation(async (...args: unknown[]) => {
        const id = String(args[0]);
        const row = rows.find((item) => item.id === id);
        return row ?? null;
      });
    const deleteSpy = jest
      .spyOn(vectorStore, "delete")
      .mockResolvedValue(undefined);
    const entityCleanupSpy = jest
      .spyOn(scopedMemory as any, "_removeMemoryFromEntityStore")
      .mockResolvedValue(undefined);

    try {
      const result = await scopedMemory.deleteAll({
        userId: "target-user",
        agentId: "agent-a",
      });

      expect(result.message).toBe("Memories deleted successfully!");
      expect(listSpy).toHaveBeenCalledWith(
        { user_id: "target-user", agent_id: "agent-a" },
        10000,
      );
      expect(deleteSpy).toHaveBeenCalledTimes(1);
      expect(deleteSpy).toHaveBeenCalledWith("owned-memory");
      expect(entityCleanupSpy).toHaveBeenCalledWith("owned-memory", {
        user_id: "target-user",
        agent_id: "agent-a",
      });
    } finally {
      listSpy.mockRestore();
      getSpy.mockRestore();
      deleteSpy.mockRestore();
      entityCleanupSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("fails closed when bulk delete cannot prove a full provider page is complete", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "qdrant";

    const vectorStore = (scopedMemory as any).vectorStore;
    const fullPage = Array.from({ length: 10000 }, (_, index) => ({
      id: `memory-${index}`,
      payload: {
        data: `target memory ${index}`,
        hash: `hash-${index}`,
        userId: "target-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));

    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([fullPage, fullPage.length])
      .mockResolvedValueOnce([[], 0]);
    const deleteSpy = jest
      .spyOn(vectorStore, "delete")
      .mockResolvedValue(undefined);
    const entityCleanupSpy = jest
      .spyOn(scopedMemory as any, "_removeMemoryFromEntityStore")
      .mockResolvedValue(undefined);

    try {
      await expect(
        scopedMemory.deleteAll({ userId: "target-user" }),
      ).rejects.toThrow(
        "deleteAll cannot safely delete all scoped memories for vector store provider 'qdrant'",
      );

      expect(listSpy).toHaveBeenCalledWith(
        { $or: [{ user_id: "target-user" }, { userId: "target-user" }] },
        10000,
      );
      expect(deleteSpy).not.toHaveBeenCalled();
      expect(entityCleanupSpy).not.toHaveBeenCalled();
    } finally {
      listSpy.mockRestore();
      deleteSpy.mockRestore();
      entityCleanupSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("fails closed before deleting when a capped cursorless provider returns its maximum page", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "vectorize";

    const vectorStore = (scopedMemory as any).vectorStore;
    const fullPage = Array.from({ length: 50 }, (_, index) => ({
      id: `memory-${index}`,
      payload: {
        data: `target memory ${index}`,
        hash: `hash-${index}`,
        user_id: "target-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));

    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([fullPage, fullPage.length]);
    const deleteSpy = jest
      .spyOn(vectorStore, "delete")
      .mockResolvedValue(undefined);
    const entityCleanupSpy = jest
      .spyOn(scopedMemory as any, "_removeMemoryFromEntityStore")
      .mockResolvedValue(undefined);

    try {
      await expect(
        scopedMemory.deleteAll({ userId: "target-user" }),
      ).rejects.toThrow(
        "deleteAll cannot safely delete all scoped memories for vector store provider 'vectorize'",
      );

      expect(listSpy).toHaveBeenNthCalledWith(
        1,
        { user_id: "target-user" },
        50,
      );
      expect(listSpy).toHaveBeenNthCalledWith(2, { userId: "target-user" }, 50);
      expect(deleteSpy).not.toHaveBeenCalled();
      expect(entityCleanupSpy).not.toHaveBeenCalled();
    } finally {
      listSpy.mockRestore();
      deleteSpy.mockRestore();
      entityCleanupSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("deletes Vectorize legacy alias-only rows in the requested scope", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "vectorize";

    const vectorStore = (scopedMemory as any).vectorStore;
    const canonicalRows = [
      {
        id: "canonical-memory",
        payload: {
          data: "canonical target memory",
          hash: "canonical-hash",
          user_id: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const legacyRows = [
      {
        id: "legacy-memory",
        payload: {
          data: "legacy target memory",
          hash: "legacy-hash",
          userId: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const listSpy = jest
      .spyOn(vectorStore, "list")
      .mockResolvedValueOnce([canonicalRows, canonicalRows.length])
      .mockResolvedValueOnce([legacyRows, legacyRows.length]);
    const deleteMemorySpy = jest
      .spyOn(scopedMemory as any, "deleteMemory")
      .mockResolvedValue(undefined);

    try {
      const result = await scopedMemory.deleteAll({ userId: "target-user" });

      expect(result.message).toBe("Memories deleted successfully!");
      expect(listSpy).toHaveBeenNthCalledWith(
        1,
        { user_id: "target-user" },
        50,
      );
      expect(listSpy).toHaveBeenNthCalledWith(2, { userId: "target-user" }, 50);
      expect(deleteMemorySpy).toHaveBeenCalledTimes(2);
      expect(deleteMemorySpy).toHaveBeenNthCalledWith(1, "canonical-memory");
      expect(deleteMemorySpy).toHaveBeenNthCalledWith(2, "legacy-memory");
    } finally {
      listSpy.mockRestore();
      deleteMemorySpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });
});

// ─── attributedTo (#5666) ────────────────────────────────

describe("Memory - attributedTo round-trip (#5666)", () => {
  let memory: Memory;
  const userId = `attributed_test_${Date.now()}`;
  let id: string;

  beforeAll(async () => {
    memory = createMemory();
    // The mocked LLM tags every extracted fact with attributed_to: "user".
    const addResult: SearchResult = await memory.add("I love AI", { userId });
    id = addResult.results[0].id;
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("get() surfaces attributedTo", async () => {
    const item: MemoryItem | null = await memory.get(id);
    expect(item!.attributedTo).toBe("user");
  });

  test("getAll() surfaces attributedTo", async () => {
    const result: SearchResult = await memory.getAll({
      filters: { user_id: userId },
    });
    expect(result.results[0].attributedTo).toBe("user");
  });

  test("search() surfaces attributedTo", async () => {
    const result: SearchResult = await memory.search("AI", {
      filters: { user_id: userId },
    });
    expect(result.results.length).toBeGreaterThan(0);
    expect(result.results[0].attributedTo).toBe("user");
  });
});

// ─── history() ───────────────────────────────────────────

describe("Memory - history()", () => {
  let memory: Memory;
  const userId = `history_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("records ADD event after add()", async () => {
    const addResult: SearchResult = await memory.add("New fact", {
      userId,
    });
    const history = await memory.history(addResult.results[0].id);
    expect(Array.isArray(history)).toBe(true);
    expect(history.length).toBeGreaterThan(0);
  });

  test("records additional entry after update()", async () => {
    const addResult: SearchResult = await memory.add("Before", {
      userId,
    });
    const id = addResult.results[0].id;
    await memory.update(id, "After");
    const history = await memory.history(id);
    expect(history.length).toBeGreaterThanOrEqual(2);
  });

  test("returns empty array for non-existent memory ID", async () => {
    const history = await memory.history("nonexistent-id");
    expect(history).toHaveLength(0);
  });
});
