/**
 * Regression test for #6101 / #5903: LLM extraction transport failures
 * (rate limits, timeouts, connection errors) must propagate as a typed
 * `LLMError`, not be silently swallowed into an empty result. Mirrors the
 * Python SDK regression test added in #5878
 * (`test_llm_extraction_exception_is_reraised`).
 */
/// <reference types="jest" />
import { Memory, LLMError } from "../src/memory";
import type { SearchResult } from "../src/types";

jest.setTimeout(15000);

// Mock Google modules to prevent @google/genai crash in CI
jest.mock("../src/embeddings/google", () => ({
  GoogleEmbedder: jest.fn(),
}));
jest.mock("../src/llms/google", () => ({
  GoogleLLM: jest.fn(),
}));

class _ProviderError extends Error {}

jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest
      .fn()
      .mockRejectedValue(new _ProviderError("429 rate limit")),
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
        collectionName: `test-llm-error-${Date.now()}`,
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

describe("Memory - LLM extraction transport failures", () => {
  let memory: Memory;
  const userId = `llm_error_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("add() rejects with LLMError instead of returning an empty result", async () => {
    await expect(
      memory.add("this should trigger a provider failure", { userId }),
    ).rejects.toBeInstanceOf(LLMError);
  });

  test("thrown LLMError preserves the original error as its cause", async () => {
    let caught: unknown;
    try {
      const result: SearchResult = await memory.add("trigger failure again", {
        userId,
      });
      // Should never reach here — fail loudly if the call resolves.
      throw new Error(
        `Expected add() to reject, but it resolved with: ${JSON.stringify(result)}`,
      );
    } catch (e) {
      caught = e;
    }

    expect(caught).toBeInstanceOf(LLMError);
    expect((caught as LLMError).cause).toBeInstanceOf(_ProviderError);
    expect((caught as LLMError).message).toContain("429 rate limit");
  });
});
