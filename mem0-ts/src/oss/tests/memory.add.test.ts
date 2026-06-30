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
        10,
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
        10,
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
        10,
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
});
