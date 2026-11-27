/**
 * OSS Memory unit tests — hash-dedup TOCTOU race in add().
 *
 * Two concurrent add() calls that extract the identical fact for the same scope
 * take their Phase-1 "existing memories" snapshot before either has inserted.
 * Without a fresh recheck under a per-scope lock right before insert, both pass
 * dedup against the same stale snapshot and both insert, producing a permanent
 * duplicate. The LLM mock is intentionally delayed to widen the race window.
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

// LLM always extracts the SAME fact, after a delay that widens the race window.
jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest.fn().mockImplementation(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
      return JSON.stringify({
        memory: [{ id: "0", text: "User likes coffee", attributed_to: "user" }],
      });
    }),
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
        collectionName: `test-dedup-race-${Date.now()}`,
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

describe("Memory - add() hash-dedup TOCTOU race", () => {
  test("two concurrent add() calls for the same fact persist only one memory", async () => {
    const memory = createMemory();
    const userId = `race_same_${Date.now()}`;

    await Promise.all([
      memory.add("I really like coffee", { userId }),
      memory.add("I really like coffee", { userId }),
    ]);

    const all: SearchResult = await memory.getAll({
      filters: { user_id: userId },
    });
    expect(all.results.length).toBe(1);

    await memory.reset();
  });

  test("concurrent add() for different scopes each persist (no false cross-scope dedup)", async () => {
    const memory = createMemory();
    const u1 = `race_u1_${Date.now()}`;
    const u2 = `race_u2_${Date.now()}`;

    await Promise.all([
      memory.add("I really like coffee", { userId: u1 }),
      memory.add("I really like coffee", { userId: u2 }),
    ]);

    const a1: SearchResult = await memory.getAll({ filters: { user_id: u1 } });
    const a2: SearchResult = await memory.getAll({ filters: { user_id: u2 } });
    expect(a1.results.length).toBe(1);
    expect(a2.results.length).toBe(1);

    await memory.reset();
  });
});
