/**
 * OSS Memory unit test — add() surfaces embedding failures instead of
 * silently dropping the affected memories.
 *
 * Regression test for #5509 (TS counterpart of the Python fix #5249 / #5245):
 * when the batch embed throws AND the per-item fallback also fails for one or
 * more texts, add() must raise an EmbeddingError rather than discarding the
 * extracted facts at `warn` level.
 */
/// <reference types="jest" />
import { Memory, EmbeddingError } from "../src/memory";
import type { MemoryConfig } from "../src/types";

jest.setTimeout(15000);

// Mock Google modules to prevent @google/genai crash in CI
jest.mock("../src/embeddings/google", () => ({
  GoogleEmbedder: jest.fn(),
}));
jest.mock("../src/llms/google", () => ({
  GoogleLLM: jest.fn(),
}));

const FACT_TEXT = "test memory fact";

jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest.fn().mockResolvedValue(
      JSON.stringify({
        memory: [{ id: "0", text: "test memory fact", attributed_to: "user" }],
      }),
    ),
  })),
}));

const mockEmbedding = new Array(1536).fill(0.1);

// Embedder where the batch path always throws (forcing the per-item fallback),
// and the per-item embed() throws ONLY for the extracted memory fact text.
// Query/probe/entity embeds still succeed, so the failure is isolated to the
// Phase 3 memory-text embedding path that previously dropped silently.
jest.mock("../src/embeddings/openai", () => ({
  OpenAIEmbedder: jest.fn().mockImplementation(() => ({
    embed: jest.fn().mockImplementation((input: unknown) => {
      const text = Array.isArray(input) ? input.join(" ") : String(input);
      if (text.includes("test memory fact")) {
        return Promise.reject(new Error("embed boom"));
      }
      return Promise.resolve(mockEmbedding);
    }),
    embedBatch: jest.fn().mockRejectedValue(new Error("embedBatch boom")),
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
        collectionName: `test-embed-fail-${Date.now()}`,
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

describe("Memory - add() embedding failure handling (#5509)", () => {
  let memory: Memory;
  const userId = `embed_fail_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    try {
      await memory.reset();
    } catch {
      // ignore cleanup errors
    }
  });

  test("throws EmbeddingError when all fallback embeds fail", async () => {
    await expect(
      memory.add("I am a software engineer", { userId }),
    ).rejects.toBeInstanceOf(EmbeddingError);
  });

  test("error message reports the dropped memory text", async () => {
    await expect(
      memory.add("I enjoy hiking in the mountains", { userId }),
    ).rejects.toThrow(/Failed to embed \d+ memory text/);
  });
});
