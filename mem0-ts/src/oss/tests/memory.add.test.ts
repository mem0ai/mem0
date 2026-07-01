/**
 * OSS Memory unit tests — add() with inference, without inference, filter validation, metadata.
 * Content-based LLM mock: system-prompt calls → facts, user-only calls → memory actions.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import type { MemoryConfig, MemoryItem, SearchResult } from "../src/types";

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

  // Regression: infer=false must skip system messages by ROLE, not by content.
  // See https://github.com/mem0ai/mem0/issues/5676 — comparing message.content
  // to "system" both (a) stored system prompts as memories and (b) dropped
  // legitimate user messages whose content happened to equal "system".
  test("with infer=false skips system messages by role, not content", async () => {
    const messages = [
      { role: "system", content: "You are a helpful assistant" },
      { role: "user", content: "I live in Berlin" },
    ];
    const result: SearchResult = await memory.add(messages, {
      userId,
      infer: false,
    });
    const stored = result.results.map((r) => r.memory);
    // System prompt must NOT be stored.
    expect(stored).not.toContain("You are a helpful assistant");
    // The user message must be stored.
    expect(stored).toContain("I live in Berlin");
  });

  test("with infer=false stores a user message whose content is 'system'", async () => {
    const messages = [{ role: "user", content: "system" }];
    const result: SearchResult = await memory.add(messages, {
      userId,
      infer: false,
    });
    // A user message with content === "system" must NOT be skipped.
    expect(result.results.map((r) => r.memory)).toContain("system");
  });
});
