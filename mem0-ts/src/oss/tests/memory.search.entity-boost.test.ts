/**
 * OSS Memory unit tests — entity-boost batching in search().
 *
 * Covers the perf fix that replaces the serial per-entity embed() loop with
 * a single embedBatch() call (with serial fallback on batch failure).
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";

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
          const userMsg = messages.find((m) => m.role === "user");
          const content = userMsg?.content ?? "";
          const newMsgMatch = content.match(
            /## New Messages\n([\s\S]*?)(?=\n##|$)/,
          );
          const extracted = newMsgMatch ? newMsgMatch[1].trim() : "stored fact";
          return JSON.stringify({
            memory: [{ id: "0", text: extracted, attributed_to: "user" }],
          });
        },
      ),
  })),
}));

// Embedder is hoisted via jest.mock — capture jest.fn() refs via a holder so
// the per-test reset works. The factory below is re-invoked each `new Memory()`
// so we expose the spies through a module-level singleton.
const embedderSpies = {
  embed: jest.fn(),
  embedBatch: jest.fn(),
};
const mockEmbedding = new Array(1536).fill(0.1);

jest.mock("../src/embeddings/openai", () => ({
  OpenAIEmbedder: jest.fn().mockImplementation(() => ({
    embed: embedderSpies.embed,
    embedBatch: embedderSpies.embedBatch,
    embeddingDims: 1536,
  })),
}));

function resetEmbedderMocks() {
  embedderSpies.embed.mockReset();
  embedderSpies.embedBatch.mockReset();
  embedderSpies.embed.mockResolvedValue(mockEmbedding);
  embedderSpies.embedBatch.mockImplementation((texts: string[]) =>
    Promise.resolve(texts.map(() => mockEmbedding)),
  );
}

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
        collectionName: `entity-boost-${Date.now()}-${Math.random()}`,
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

// Query intentionally crafted to surface ≥5 distinct entities through
// extractEntities(): period-separated sentences prevent the NLP compound
// extractor from collapsing the list into a single noun phrase.
const MULTI_ENTITY_QUERY =
  'Tell me about "Alice". And "Bob". And "Carol". And "Dave". And "Eve" at "Acme Corp".';

describe("Memory.search() — entity boost embedding batching", () => {
  let memory: Memory;
  const userId = `entity_boost_${Date.now()}`;

  beforeEach(async () => {
    resetEmbedderMocks();
    memory = createMemory();
    // Seed a memory so extractEntities/entity-store have content to land on.
    await memory.add(
      "Alice and Bob work at Acme Corp with Carol, Dave, and Eve.",
      { userId },
    );
  });

  afterEach(async () => {
    await memory.reset();
  });

  test("calls embedBatch once with all deduped entity texts; embed only for the query", async () => {
    const embedCallsBefore = embedderSpies.embed.mock.calls.length;
    const embedBatchCallsBefore = embedderSpies.embedBatch.mock.calls.length;

    await memory.search(MULTI_ENTITY_QUERY, {
      filters: { user_id: userId },
    });

    const newEmbedCalls = embedderSpies.embed.mock.calls.slice(embedCallsBefore);
    const newEmbedBatchCalls = embedderSpies.embedBatch.mock.calls.slice(
      embedBatchCallsBefore,
    );

    // Query embedding is the only single-text embed() invoked by search().
    expect(newEmbedCalls).toHaveLength(1);
    expect(newEmbedCalls[0][0]).toBe(MULTI_ENTITY_QUERY);

    // Entity embeddings are batched into a single embedBatch() call.
    expect(newEmbedBatchCalls).toHaveLength(1);
    const batchTexts = newEmbedBatchCalls[0][0] as string[];
    expect(Array.isArray(batchTexts)).toBe(true);
    expect(batchTexts.length).toBeGreaterThanOrEqual(5);
    // Batch obeys the .slice(0, 8) cap.
    expect(batchTexts.length).toBeLessThanOrEqual(8);
  });

  test("falls back to serial embed() when embedBatch throws", async () => {
    // Drop one embedBatch invocation; subsequent calls return normally.
    embedderSpies.embedBatch.mockRejectedValueOnce(
      new Error("simulated batch failure"),
    );

    const embedCallsBefore = embedderSpies.embed.mock.calls.length;

    const result = await memory.search(MULTI_ENTITY_QUERY, {
      filters: { user_id: userId },
    });

    const newEmbedCalls = embedderSpies.embed.mock.calls.slice(embedCallsBefore);

    // First embed call is for the query itself; the remainder are the
    // per-entity fallback after embedBatch failure.
    expect(newEmbedCalls.length).toBeGreaterThan(1);
    expect(newEmbedCalls[0][0]).toBe(MULTI_ENTITY_QUERY);

    const fallbackCalls = newEmbedCalls.slice(1);
    expect(fallbackCalls.length).toBeGreaterThanOrEqual(5);
    expect(fallbackCalls.length).toBeLessThanOrEqual(8);
    for (const call of fallbackCalls) {
      expect(typeof call[0]).toBe("string");
    }

    // Search still completes with valid results despite the batch failure.
    expect(result).toBeDefined();
    expect(Array.isArray(result.results)).toBe(true);
  });

  test("survives individual entity embed failures in the fallback path", async () => {
    embedderSpies.embedBatch.mockRejectedValueOnce(
      new Error("batch broken"),
    );
    // Query embed succeeds; second entity embed throws; rest succeed.
    let callIdx = 0;
    embedderSpies.embed.mockImplementation((text: string) => {
      const i = callIdx++;
      // i=0 is the query; i=2 simulates a transient per-entity failure.
      if (i === 2) return Promise.reject(new Error("entity embed failed"));
      return Promise.resolve(mockEmbedding);
    });

    // Must not throw — fallback path tolerates individual failures.
    const result = await memory.search(MULTI_ENTITY_QUERY, {
      filters: { user_id: userId },
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.results)).toBe(true);
  });

  test("does not call embedBatch when query yields no entities", async () => {
    const embedBatchBefore = embedderSpies.embedBatch.mock.calls.length;
    // Lowercase, no proper nouns ⇒ extractEntities() returns empty.
    await memory.search("what time is it", {
      filters: { user_id: userId },
    });
    const newBatchCalls = embedderSpies.embedBatch.mock.calls.slice(
      embedBatchBefore,
    );
    expect(newBatchCalls).toHaveLength(0);
  });
});
