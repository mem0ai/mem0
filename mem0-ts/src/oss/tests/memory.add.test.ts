/**
 * OSS Memory unit tests — add() with inference, without inference, filter validation, metadata.
 * Content-based LLM mock: system-prompt calls → facts, user-only calls → memory actions.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import type { MemoryConfig, MemoryItem, SearchResult } from "../src/types";
import { createHash } from "crypto";

jest.setTimeout(15000);

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
          const userMsg = messages.find((m) => m.role === "user");
          const content = userMsg?.content ?? "";
          const newMsgMatch = content.match(
            /## New Messages\n([\s\S]*?)(?=\n##|$)/,
          );
          const extracted = newMsgMatch
            ? newMsgMatch[1].trim()
            : "extracted fact from input";
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

function createMemory(overrides: Partial<MemoryConfig> = {}): Memory {
  return new Memory({
    version: "v1.1",
    embedder: {
      provider: "openai",
      config: { apiKey: "test-key", model: "text-embedding-3-small" },
    },
    vectorStore: {
      provider: "memory",
      config: {
        collectionName: `test-add-${Date.now()}`,
        dimension: 1536,
        dbPath: ":memory:",
      },
    },
    llm: {
      provider: "openai",
      config: { apiKey: "test-key", model: "gpt-5-mini" },
    },
    historyDbPath: ":memory:",
    ...overrides,
  });
}

describe("Memory - add()", () => {
  let memory: Memory;
  const userId = `add_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("returns SearchResult with results array for string input", async () => {
    const result: SearchResult = await memory.add("I am a software engineer", {
      userId,
    });
    expect(Array.isArray(result.results)).toBe(true);
  });

  test("returns at least one result with an id", async () => {
    const result: SearchResult = await memory.add(
      "I enjoy hiking in the mountains",
      { userId },
    );
    expect(result.results.length).toBeGreaterThan(0);
    expect(result.results[0].id).toBeDefined();
  });

  test("result item has a memory string field", async () => {
    const result: SearchResult = await memory.add("My favorite color is blue", {
      userId,
    });
    expect(typeof result.results[0].memory).toBe("string");
  });

  test("accepts Message[] input", async () => {
    const messages = [
      { role: "user", content: "What is your favorite city?" },
      { role: "assistant", content: "I love Paris." },
    ];
    const result: SearchResult = await memory.add(messages, { userId });
    expect(result.results.length).toBeGreaterThan(0);
  });

  test("preserves message roles in the extraction prompt (## New Messages)", async () => {
    // The OpenAI LLM mock echoes the `## New Messages` section of the prompt back
    // as the extracted text, so the stored memory reveals what the LLM received.
    // Roles must survive into that section, otherwise the prompt's role-aware
    // logic and required `attributed_to` output have no speaker to attribute to
    // and assistant statements get stored as user facts.
    const messages = [
      { role: "user", content: "I want to sleep earlier." },
      { role: "assistant", content: "Aim for 00:30 sleep / 08:30 wake." },
    ];
    const result: SearchResult = await memory.add(messages, { userId });
    const seen = result.results.map((r) => r.memory).join("\n");
    expect(seen).toContain("user: I want to sleep earlier.");
    expect(seen).toContain("assistant: Aim for 00:30 sleep / 08:30 wake.");
  });

  test("works with agentId instead of userId", async () => {
    const result: SearchResult = await memory.add("test", {
      agentId: "agent_1",
    });
    expect(result.results.length).toBeGreaterThan(0);
  });

  test("works with runId instead of userId", async () => {
    const result: SearchResult = await memory.add("test", { runId: "run_1" });
    expect(result.results.length).toBeGreaterThan(0);
  });

  test("throws when no userId/agentId/runId provided", async () => {
    await expect(memory.add("test", {} as any)).rejects.toThrow(
      "One of the filters: userId, agentId or runId is required!",
    );
  });

  test.each([
    [
      "wildcard",
      { user_id: "*" },
      "Wildcard scope filters [user_id] are not supported in add()",
    ],
    [
      "array shorthand",
      { user_id: ["target-user", "other-user"] },
      "Scope filter [user_id] in add() must use explicit equality",
    ],
    [
      "negative operator",
      { user_id: { ne: "other-user" } },
      "Scope filter [user_id] in add() must use explicit equality",
    ],
    [
      "nin operator",
      { user_id: { nin: ["other-user"] } },
      "Scope filter [user_id] in add() must use explicit equality",
    ],
    [
      "negative logical scope",
      { user_id: "target-user", NOT: [{ agent_id: "blocked-agent" }] },
      "Negative scope filters [agent_id] are not supported in add()",
    ],
  ])(
    "rejects broad %s scope filters before inferred existing-memory search",
    async (_name, filters, message) => {
      const scopedMemory = createMemory();
      await (scopedMemory as any)._ensureInitialized();

      const vectorStore = (scopedMemory as any).vectorStore;
      const searchSpy = jest.spyOn(vectorStore, "search");

      try {
        await expect(
          scopedMemory.add("I love carefully scoped sushi.", {
            filters,
          } as any),
        ).rejects.toThrow(message);

        expect(searchSpy).not.toHaveBeenCalled();
      } finally {
        searchSpy.mockRestore();
        await scopedMemory.reset();
      }
    },
  );

  test("stores scope metadata when add scope is supplied via filters", async () => {
    const scopedMemory = createMemory();

    try {
      const result: SearchResult = await scopedMemory.add(
        "I love filter-only sushi.",
        {
          filters: { user_id: "target-user" },
        },
      );

      expect(result.results).toHaveLength(1);
      const stored = await scopedMemory.get(result.results[0].id);
      expect(stored).toEqual(
        expect.objectContaining({ user_id: "target-user" }),
      );
    } finally {
      await scopedMemory.reset();
    }
  });

  test("rejects reserved scope metadata that conflicts with requested add scope", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const insertSpy = jest.spyOn(vectorStore, "insert");

    try {
      await expect(
        scopedMemory.add("Direct conflicting scope metadata", {
          filters: { user_id: "target-user" },
          metadata: { userId: "other-user", source: "chat" },
          infer: false,
        }),
      ).rejects.toThrow(
        "Metadata field [userId] conflicts with requested user_id scope in add()",
      );

      expect(insertSpy).not.toHaveBeenCalled();
    } finally {
      insertSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("rejects metadata with conflicting canonical and alias scope values", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const insertSpy = jest.spyOn(vectorStore, "insert");

    try {
      await expect(
        scopedMemory.add("Direct internally conflicting scope metadata", {
          filters: { user_id: "target-user" },
          metadata: {
            user_id: "target-user",
            userId: "other-user",
            source: "chat",
          },
          infer: false,
        }),
      ).rejects.toThrow(
        "Metadata field [userId] conflicts with requested user_id scope in add()",
      );

      expect(insertSpy).not.toHaveBeenCalled();
    } finally {
      insertSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("stores authoritative canonical scope when metadata repeats the same scope", async () => {
    const scopedMemory = createMemory();

    try {
      const result: SearchResult = await scopedMemory.add(
        "Direct matching scope metadata",
        {
          filters: { user_id: "target-user" },
          metadata: { userId: "target-user", source: "chat" },
          infer: false,
        },
      );

      const stored = await scopedMemory.get(result.results[0].id);
      expect(stored).toEqual(
        expect.objectContaining({
          user_id: "target-user",
          metadata: { source: "chat" },
        }),
      );
      expect(stored!.metadata).not.toHaveProperty("userId");
      expect(stored!.metadata).not.toHaveProperty("user_id");
    } finally {
      await scopedMemory.reset();
    }
  });

  test.each([
    ["wildcard", { user_id: "*" }],
    ["ne", { user_id: { ne: "other-user" } }],
    ["in", { user_id: { in: ["target-user"] } }],
    ["range", { user_id: { gt: "other-user" } }],
    ["conflicting alias", { user_id: "target-user", userId: "other-user" }],
  ])(
    "rejects top-level scope with malformed same-key %s filter before add search",
    async (_name, filters) => {
      const scopedMemory = createMemory();
      await (scopedMemory as any)._ensureInitialized();

      const vectorStore = (scopedMemory as any).vectorStore;
      const searchSpy = jest.spyOn(vectorStore, "search");

      try {
        await expect(
          scopedMemory.add("I love carefully scoped sushi.", {
            userId: "target-user",
            filters,
          } as any),
        ).rejects.toThrow(
          "Conflicting scope filters [user_id] are not supported in add()",
        );

        expect(searchSpy).not.toHaveBeenCalled();
      } finally {
        searchSpy.mockRestore();
        await scopedMemory.reset();
      }
    },
  );

  test("rejects conflicting top-level and filter scopes before add search", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search");

    try {
      await expect(
        scopedMemory.add("I love carefully scoped sushi.", {
          userId: "target-user",
          filters: { user_id: "other-user" },
        }),
      ).rejects.toThrow(
        "Conflicting scope filters [user_id] are not supported in add()",
      );

      expect(searchSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("rejects overly complex scope filters before add search", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search");
    let nested: Record<string, any> = { topic: "travel" };
    for (let i = 0; i < 40; i += 1) {
      nested = { AND: [nested] };
    }

    try {
      await expect(
        scopedMemory.add("I love carefully scoped sushi.", {
          filters: { user_id: "target-user", AND: [nested] },
        }),
      ).rejects.toThrow("Scope filter is too complex to safely evaluate");

      expect(searchSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("rejects malformed logical filters before add search", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search");
    const insertSpy = jest.spyOn(vectorStore, "insert");

    try {
      await expect(
        scopedMemory.add("I love carefully scoped sushi.", {
          filters: {
            user_id: "target-user",
            NOT: { topic: "secret" },
          } as any,
        }),
      ).rejects.toThrow("NOT operator requires a non-empty list of conditions");

      expect(searchSpy).not.toHaveBeenCalled();
      expect(insertSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      insertSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("uses canonical scope internally when add scope is supplied via camelCase filters", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const entityStore = {
      list: jest.fn().mockResolvedValue([[], 0]),
      search: jest.fn().mockResolvedValue([]),
      insert: jest.fn().mockResolvedValue(undefined),
      update: jest.fn().mockResolvedValue(undefined),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
    (scopedMemory as any)._entityStore = entityStore;

    const db = (scopedMemory as any).db;
    const getLastMessagesSpy = jest
      .spyOn(db, "getLastMessages")
      .mockResolvedValue([]);

    try {
      const result: SearchResult = await scopedMemory.add(
        'Alice Liddell discussed "Project Hailstorm" with Bob Stone.',
        {
          filters: { userId: "target-user" },
        },
      );

      expect(result.results).toHaveLength(1);
      expect(getLastMessagesSpy).toHaveBeenCalledWith(
        "user_id=target-user",
        10,
      );

      const stored = await scopedMemory.get(result.results[0].id);
      expect(stored).toEqual(
        expect.objectContaining({ user_id: "target-user" }),
      );

      expect(entityStore.list).toHaveBeenCalledWith(
        { user_id: "target-user" },
        10000,
      );
      expect(entityStore.search).toHaveBeenCalledWith(expect.any(Array), 1, {
        user_id: "target-user",
      });
      expect(entityStore.insert).toHaveBeenCalled();
      const lastInsertCall =
        entityStore.insert.mock.calls[entityStore.insert.mock.calls.length - 1];
      const payloads = lastInsertCall[2] as Array<Record<string, any>>;
      expect(payloads.length).toBeGreaterThan(0);
      for (const payload of payloads) {
        expect(payload.user_id).toBe("target-user");
      }
    } finally {
      getLastMessagesSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("passes metadata through to stored memory", async () => {
    const result: SearchResult = await memory.add("I love TypeScript", {
      userId,
      metadata: { source: "chat", tag: "programming" },
    });
    const stored: MemoryItem | null = await memory.get(result.results[0].id);
    expect(stored).not.toBeNull();
    expect(stored!.metadata).toEqual(
      expect.objectContaining({ source: "chat", tag: "programming" }),
    );
  });

  test("with infer=false skips LLM and stores messages directly", async () => {
    const result: SearchResult = await memory.add("Direct storage content", {
      userId,
      infer: false,
    });
    expect(result.results.length).toBeGreaterThan(0);
    // When infer=false, the literal message text is stored
    expect(result.results[0].memory).toBe("Direct storage content");
  });

  test("with infer=false marks event as ADD in metadata", async () => {
    const result: SearchResult = await memory.add("Direct fact", {
      userId,
      infer: false,
    });
    expect(result.results[0].metadata).toEqual(
      expect.objectContaining({ event: "ADD" }),
    );
  });

  test("ignores wrong-scope existing search results when deduplicating inferred memories", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const extractedText = "user: I love carefully scoped sushi.";
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "foreign-memory",
        score: 0.99,
        payload: {
          data: extractedText,
          hash: createHash("md5").update(extractedText).digest("hex"),
          user_id: "other-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);

    try {
      const result: SearchResult = await scopedMemory.add(
        "I love carefully scoped sushi.",
        { userId: "target-user" },
      );

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        60,
        expect.objectContaining({ user_id: "target-user" }),
      );
      expect(result.results).toHaveLength(1);
      expect(result.results[0].memory).toBe(extractedText);
      const stored = await scopedMemory.get(result.results[0].id);
      expect((stored as any).user_id).toBe("target-user");
    } finally {
      searchSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("fails closed when inferred dedupe search cannot prove scoped completeness", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const foreignRows = Array.from({ length: 60 }, (_, index) => ({
      id: `foreign-memory-${index}`,
      score: 1 - index / 1000,
      payload: {
        data: `foreign duplicate candidate ${index}`,
        hash: createHash("md5")
          .update(`foreign duplicate candidate ${index}`)
          .digest("hex"),
        user_id: "other-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));
    const searchSpy = jest
      .spyOn(vectorStore, "search")
      .mockResolvedValueOnce(foreignRows)
      .mockResolvedValueOnce([]);
    const insertSpy = jest.spyOn(vectorStore, "insert");

    try {
      await expect(
        scopedMemory.add("I love carefully scoped sushi.", {
          userId: "target-user",
        }),
      ).rejects.toThrow(
        "add cannot safely infer scoped memories for vector store provider 'memory'",
      );

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        60,
        expect.objectContaining({ user_id: "target-user" }),
      );
      expect(insertSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      insertSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("fails closed when a capped provider returns its maximum search page during inferred dedupe", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "vectorize";

    const vectorStore = (scopedMemory as any).vectorStore;
    const foreignRows = Array.from({ length: 50 }, (_, index) => ({
      id: `foreign-memory-${index}`,
      score: 1 - index / 1000,
      payload: {
        data: `foreign duplicate candidate ${index}`,
        hash: createHash("md5")
          .update(`foreign duplicate candidate ${index}`)
          .digest("hex"),
        user_id: "other-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));
    const searchSpy = jest
      .spyOn(vectorStore, "search")
      .mockResolvedValueOnce(foreignRows);
    const insertSpy = jest.spyOn(vectorStore, "insert");

    try {
      await expect(
        scopedMemory.add("I love carefully scoped sushi.", {
          userId: "target-user",
        }),
      ).rejects.toThrow(
        "add cannot safely infer scoped memories for vector store provider 'vectorize'",
      );

      expect(searchSpy).toHaveBeenNthCalledWith(
        1,
        mockEmbedding,
        50,
        expect.objectContaining({ user_id: "target-user" }),
      );
      expect(searchSpy).toHaveBeenNthCalledWith(
        2,
        mockEmbedding,
        50,
        expect.objectContaining({ userId: "target-user" }),
      );
      expect(insertSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      insertSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("keeps inferred dedupe prompt context capped after scoped over-fetching", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = Array.from({ length: 12 }, (_, index) => ({
      id: `owned-memory-${index}`,
      score: 1 - index / 1000,
      payload: {
        data: `existing scoped memory ${index}`,
        hash: createHash("md5")
          .update(`existing scoped memory ${index}`)
          .digest("hex"),
        user_id: "target-user",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    }));
    const searchSpy = jest
      .spyOn(vectorStore, "search")
      .mockResolvedValueOnce(rows);
    const llmGenerateSpy = jest.spyOn(
      (scopedMemory as any).llm,
      "generateResponse",
    );

    try {
      await scopedMemory.add("I love carefully scoped sushi.", {
        userId: "target-user",
      });

      const llmMessages = llmGenerateSpy.mock.calls[0][0] as Array<{
        role: string;
        content: string;
      }>;
      const userPrompt = llmMessages.find(
        (message) => message.role === "user",
      )?.content;

      expect(userPrompt).toContain("existing scoped memory 9");
      expect(userPrompt).not.toContain("existing scoped memory 10");
      expect(userPrompt).not.toContain("existing scoped memory 11");
    } finally {
      searchSpy.mockRestore();
      llmGenerateSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("keeps logical metadata filtering in inferred context for simple providers", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "redis";

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "wrong-topic-memory",
        score: 0.99,
        payload: {
          data: "same user wrong topic",
          hash: createHash("md5").update("same user wrong topic").digest("hex"),
          userId: "target-user",
          topic: "food",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "topic-match-memory",
        score: 0.98,
        payload: {
          data: "same user travel memory",
          hash: createHash("md5")
            .update("same user travel memory")
            .digest("hex"),
          userId: "target-user",
          topic: "travel",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const searchSpy = jest
      .spyOn(vectorStore, "search")
      .mockResolvedValueOnce(rows);
    const llmGenerateSpy = jest.spyOn(
      (scopedMemory as any).llm,
      "generateResponse",
    );

    try {
      await scopedMemory.add("I love carefully scoped sushi.", {
        userId: "target-user",
        filters: { OR: [{ topic: "travel" }, { agent_id: "agent-a" }] },
      });

      expect(searchSpy).toHaveBeenCalledWith(mockEmbedding, 60, {
        user_id: "target-user",
      });

      const llmMessages = llmGenerateSpy.mock.calls[0][0] as Array<{
        role: string;
        content: string;
      }>;
      const userPrompt = llmMessages.find(
        (message) => message.role === "user",
      )?.content;

      expect(userPrompt).toContain("same user travel memory");
      expect(userPrompt).not.toContain("same user wrong topic");
    } finally {
      searchSpy.mockRestore();
      llmGenerateSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("keeps advanced metadata filtering in inferred context for simple providers", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "redis";

    const vectorStore = (scopedMemory as any).vectorStore;
    const rows = [
      {
        id: "wrong-topic-memory",
        score: 0.99,
        payload: {
          data: "same user wrong topic",
          hash: createHash("md5").update("same user wrong topic").digest("hex"),
          userId: "target-user",
          topic: "food",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
      {
        id: "topic-match-memory",
        score: 0.98,
        payload: {
          data: "same user travel memory",
          hash: createHash("md5")
            .update("same user travel memory")
            .digest("hex"),
          userId: "target-user",
          topic: "travel plans",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ];
    const searchSpy = jest
      .spyOn(vectorStore, "search")
      .mockResolvedValueOnce(rows);
    const llmGenerateSpy = jest.spyOn(
      (scopedMemory as any).llm,
      "generateResponse",
    );

    try {
      await scopedMemory.add("I love carefully scoped sushi.", {
        userId: "target-user",
        filters: { topic: { contains: "travel" } },
      });

      expect(searchSpy).toHaveBeenCalledWith(mockEmbedding, 60, {
        user_id: "target-user",
      });

      const llmMessages = llmGenerateSpy.mock.calls[0][0] as Array<{
        role: string;
        content: string;
      }>;
      const userPrompt = llmMessages.find(
        (message) => message.role === "user",
      )?.content;

      expect(userPrompt).toContain("same user travel memory");
      expect(userPrompt).not.toContain("same user wrong topic");
    } finally {
      searchSpy.mockRestore();
      llmGenerateSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("uses camelCase scoped existing search results when deduplicating inferred memories", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const extractedText = "user: I love Redis-compatible sushi.";
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "owned-memory",
        score: 0.99,
        payload: {
          data: extractedText,
          hash: createHash("md5").update(extractedText).digest("hex"),
          userId: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const insertSpy = jest.spyOn(vectorStore, "insert");

    try {
      const result: SearchResult = await scopedMemory.add(
        "I love Redis-compatible sushi.",
        { userId: "target-user" },
      );

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        60,
        expect.objectContaining({ user_id: "target-user" }),
      );
      expect(result.results).toHaveLength(0);
      expect(insertSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      insertSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("uses Vectorize legacy alias scoped results when deduplicating inferred memories", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    (scopedMemory as any).config.vectorStore.provider = "vectorize";

    const vectorStore = (scopedMemory as any).vectorStore;
    const extractedText = "user: I love Vectorize-compatible sushi.";
    const searchSpy = jest
      .spyOn(vectorStore, "search")
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          id: "legacy-owned-memory",
          score: 0.99,
          payload: {
            data: extractedText,
            hash: createHash("md5").update(extractedText).digest("hex"),
            userId: "target-user",
            createdAt: "2026-01-01T00:00:00.000Z",
          },
        },
      ]);
    const insertSpy = jest.spyOn(vectorStore, "insert");

    try {
      const result: SearchResult = await scopedMemory.add(
        "I love Vectorize-compatible sushi.",
        { userId: "target-user" },
      );

      expect(searchSpy).toHaveBeenNthCalledWith(
        1,
        mockEmbedding,
        50,
        expect.objectContaining({ user_id: "target-user" }),
      );
      expect(searchSpy).toHaveBeenNthCalledWith(
        2,
        mockEmbedding,
        50,
        expect.objectContaining({ userId: "target-user" }),
      );
      expect(result.results).toHaveLength(0);
      expect(insertSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      insertSpy.mockRestore();
      (scopedMemory as any).config.vectorStore.provider = "memory";
      await scopedMemory.reset();
    }
  });

  test("prefers canonical scope over conflicting camelCase aliases during dedupe", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const extractedText = "user: I love canonical sushi.";
    const searchSpy = jest.spyOn(vectorStore, "search").mockResolvedValueOnce([
      {
        id: "conflicting-memory",
        score: 0.99,
        payload: {
          data: extractedText,
          hash: createHash("md5").update(extractedText).digest("hex"),
          user_id: "other-user",
          userId: "target-user",
          createdAt: "2026-01-01T00:00:00.000Z",
        },
      },
    ]);
    const insertSpy = jest.spyOn(vectorStore, "insert");

    try {
      const result: SearchResult = await scopedMemory.add(
        "I love canonical sushi.",
        { userId: "target-user" },
      );

      expect(searchSpy).toHaveBeenCalledWith(
        mockEmbedding,
        60,
        expect.objectContaining({ user_id: "target-user" }),
      );
      expect(result.results).toHaveLength(1);
      expect(result.results[0].memory).toBe(extractedText);
      expect(insertSpy).toHaveBeenCalledTimes(1);
    } finally {
      searchSpy.mockRestore();
      insertSpy.mockRestore();
      await scopedMemory.reset();
    }
  });

  test("rejects conflicting add scope aliases before persistence", async () => {
    const scopedMemory = createMemory();
    await (scopedMemory as any)._ensureInitialized();

    const vectorStore = (scopedMemory as any).vectorStore;
    const searchSpy = jest.spyOn(vectorStore, "search");
    const insertSpy = jest.spyOn(vectorStore, "insert");

    try {
      await expect(
        scopedMemory.add("I love conflicting sushi.", {
          filters: { user_id: "canonical-user", userId: "alias-user" },
        }),
      ).rejects.toThrow("Conflicting scope filters [user_id]");

      expect(searchSpy).not.toHaveBeenCalled();
      expect(insertSpy).not.toHaveBeenCalled();
    } finally {
      searchSpy.mockRestore();
      insertSpy.mockRestore();
      await scopedMemory.reset();
    }
  });
});
