/**
 * OSS Memory unit tests — constructor, initialization, config validation, reset.
 * Mocks LLM/Embedder at module level. No API keys needed.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import type { MemoryConfig, SearchResult } from "../src/types";

jest.setTimeout(15000);

// Mock Google modules to prevent @google/genai crash in CI
jest.mock("../src/embeddings/google", () => ({
  GoogleEmbedder: jest.fn(),
}));
jest.mock("../src/llms/google", () => ({
  GoogleLLM: jest.fn(),
}));

// ─── Content-based LLM mock (V3 additive extraction pipeline) ─────────
jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest
      .fn()
      .mockImplementation(
        (messages: Array<{ role: string; content: string }>) => {
          const userMsg = messages.find((m) => m.role === "user");
          const content = userMsg?.content ?? "";
          const newMsgMatch = content.match(
            /## New Messages\n([\s\S]*?)(?=\n##|$)/,
          );
          const extracted = newMsgMatch ? newMsgMatch[1].trim() : "test fact";
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
      config: { collectionName: "test-init", dimension: 1536 },
    },
    llm: {
      provider: "openai",
      config: { apiKey: "test-key", model: "gpt-5-mini" },
    },
    historyDbPath: ":memory:",
    ...overrides,
  });
}

describe("Memory - Initialization", () => {
  test("constructs without throwing with valid config", () => {
    expect(() => createMemory()).not.toThrow();
  });

  test("fromConfig creates instance from config dict", () => {
    const config = {
      version: "v1.1",
      embedder: {
        provider: "openai",
        config: { apiKey: "test-key", model: "text-embedding-3-small" },
      },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test", dimension: 1536 },
      },
      llm: {
        provider: "openai",
        config: { apiKey: "test-key", model: "gpt-5-mini" },
      },
    };
    const mem = Memory.fromConfig(config);
    expect(mem).toBeInstanceOf(Memory);
  });

  test("fromConfig throws on invalid config", () => {
    expect(() => Memory.fromConfig({ invalid: true } as any)).toThrow();
  });

  test("disableHistory=true uses DummyHistoryManager (no crash on history)", async () => {
    const mem = createMemory({ disableHistory: true });
    // If DummyHistoryManager is used, history returns [] without error
    const result = await mem.history("nonexistent-id");
    expect(Array.isArray(result)).toBe(true);
  });
});

describe("Memory - reset()", () => {
  test("reset clears all stored memories", async () => {
    const mem = createMemory();
    const userId = `reset_test_${Date.now()}`;

    await mem.add("Remember this fact", { userId });
    const before: SearchResult = await mem.getAll({
      filters: { user_id: userId },
    });
    expect(before.results.length).toBeGreaterThan(0);

    await mem.reset();

    const after: SearchResult = await mem.getAll({
      filters: { user_id: userId },
    });
    expect(after.results).toHaveLength(0);
  });
});
