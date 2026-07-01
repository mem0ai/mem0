/**
 * OSS Memory unit test — preserve-then-raise + validation classification (#5509).
 *
 * Two extracted facts. One embeds fine, one fails. add() must:
 *  - PERSIST the successful memory (not throw it away), then
 *  - raise EmbeddingError carrying failedTexts (the failed one only),
 *    persistedCount === 1, and the right errorClass.
 *
 * Also covers the validation half: a returned NON-FINITE vector (NaN) is not
 * persisted and is classified `validation`, which outranks `provider`.
 */
/// <reference types="jest" />
import { Memory, EmbeddingError } from "../src/memory";
import type { MemoryConfig } from "../src/types";

jest.setTimeout(15000);

jest.mock("../src/embeddings/google", () => ({
  GoogleEmbedder: jest.fn(),
}));
jest.mock("../src/llms/google", () => ({
  GoogleLLM: jest.fn(),
}));

const GOOD = "I live in Tennessee";
const BAD = "I work in regenerative agriculture";
const NAN = "this one returns a NaN vector";

const okVec = new Array(8).fill(0.1);

// LLM extracts three facts: one good, one whose embed throws, one whose embed
// returns a NaN vector.
jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest.fn().mockResolvedValue(
      JSON.stringify({
        memory: [
          { id: "0", text: "I live in Tennessee", attributed_to: "user" },
          {
            id: "1",
            text: "I work in regenerative agriculture",
            attributed_to: "user",
          },
          {
            id: "2",
            text: "this one returns a NaN vector",
            attributed_to: "user",
          },
        ],
      }),
    ),
  })),
}));

// Batch always throws -> force per-item fallback. Per item:
//  - GOOD  -> valid 8-dim vector
//  - BAD   -> throws (provider-class)
//  - NAN   -> returns a vector containing NaN (validation-class)
//  - any other text (probe/query/entity) -> valid vector
jest.mock("../src/embeddings/openai", () => ({
  OpenAIEmbedder: jest.fn().mockImplementation(() => ({
    embed: jest.fn().mockImplementation((input: unknown) => {
      const text = Array.isArray(input) ? input.join(" ") : String(input);
      if (text.includes("regenerative agriculture")) {
        return Promise.reject(new Error("provider 503"));
      }
      if (text.includes("NaN vector")) {
        return Promise.resolve([0.1, 0.2, NaN, 0.4, 0.5, 0.6, 0.7, 0.8]);
      }
      return Promise.resolve(okVec);
    }),
    embedBatch: jest.fn().mockRejectedValue(new Error("batch unavailable")),
    embeddingDims: 8,
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
        collectionName: `test-embed-partial-${Date.now()}`,
        dimension: 8,
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

describe("Memory - add() preserve-then-raise + validation (#5509)", () => {
  let memory: Memory;
  const userId = `embed_partial_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    try {
      await memory.reset();
    } catch {
      // ignore
    }
  });

  test("persists the good memory, raises with only the failed ones, validation outranks provider", async () => {
    let err: EmbeddingError | null = null;
    try {
      await memory.add("tell me about myself", { userId });
    } catch (e) {
      err = e as EmbeddingError;
    }

    expect(err).toBeInstanceOf(EmbeddingError);
    // one good fact persisted, two failed (provider + validation)
    expect(err!.persistedCount).toBe(1);
    expect(err!.failedTexts).toEqual(expect.arrayContaining([BAD, NAN]));
    expect(err!.failedTexts).not.toContain(GOOD);
    // validation is the more dangerous half and must win the collapse
    expect(err!.errorClass).toBe("validation");

    // The good memory really was written, despite the raise.
    const all = await memory.getAll({ filters: { user_id: userId } });
    const memories = Array.isArray(all) ? all : ((all as any).results ?? []);
    const texts = memories.map((m: any) => m.memory);
    expect(texts).toContain(GOOD);
    // the NaN vector must NOT have been persisted
    expect(texts).not.toContain(NAN);
  });
});
