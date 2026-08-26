/**
 * Deduplication search window tests for Memory.add() (#7123).
 *
 * The pre-extraction similarity search used to be hardcoded to the top-10
 * nearest memories with no similarity threshold. These tests verify the new
 * `dedupSearchLimit` and `dedupSearchThreshold` config options: with a
 * threshold set, dissimilar memories are excluded from the LLM extraction
 * context; without it, behavior is unchanged.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import { ConfigManager } from "../src/config/manager";

jest.setTimeout(15000);

jest.mock("../src/embeddings/google", () => ({
  GoogleEmbedder: jest.fn(),
}));
jest.mock("../src/llms/google", () => ({
  GoogleLLM: jest.fn(),
}));

const promptCapture: { lastUserPrompt: string } = { lastUserPrompt: "" };
let extractionQueue: Array<Array<{ text: string }>> = [];

jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest
      .fn()
      .mockImplementation((messages: Array<{ role: string; content: string }>) => {
        promptCapture.lastUserPrompt =
          messages.find((m) => m.role === "user")?.content ?? "";
        const next = extractionQueue.shift() ?? [];
        return Promise.resolve(JSON.stringify({ memory: next }));
      }),
  })),
}));

// Deterministic two-direction embedding space: texts mentioning "coffee"
// map to one axis, everything else to an orthogonal axis.
const AXIS_COFFEE = [1, 0, 0, 0, 0, 0, 0, 0];
const AXIS_OTHER = [0, 1, 0, 0, 0, 0, 0, 0];

jest.mock("../src/embeddings/openai", () => ({
  OpenAIEmbedder: jest.fn().mockImplementation(() => ({
    embed: jest.fn().mockImplementation((text: string) =>
      Promise.resolve(text.includes("coffee") ? AXIS_COFFEE : AXIS_OTHER),
    ),
    embedBatch: jest.fn().mockImplementation((texts: string[]) =>
      Promise.resolve(
        texts.map((t) => (t.includes("coffee") ? AXIS_COFFEE : AXIS_OTHER)),
      ),
    ),
    embeddingDims: 8,
  })),
}));

function createMemory(config: Record<string, any> = {}): Memory {
  return new Memory({
    embedder: {
      provider: "openai",
      config: { apiKey: "test-key", model: "text-embedding-3-small" },
    },
    vectorStore: {
      provider: "memory",
      config: {
        collectionName: `test-dedup-${Date.now()}-${Math.random()}`,
        dimension: 8,
      },
    },
    llm: {
      provider: "openai",
      config: { apiKey: "test-key", model: "gpt-5-mini" },
    },
    ...config,
  } as any);
}

describe("add() dedup search options (#7123)", () => {
  beforeEach(() => {
    promptCapture.lastUserPrompt = "";
    extractionQueue = [];
  });

  it("mergeConfig passes dedup options through", () => {
    const merged = ConfigManager.mergeConfig({
      dedupSearchLimit: 25,
      dedupSearchThreshold: 0.4,
    } as any);
    expect(merged.dedupSearchLimit).toBe(25);
    expect(merged.dedupSearchThreshold).toBe(0.4);
  });

  it("without a threshold the dissimilar memory stays in the extraction context", async () => {
    const memory = createMemory();

    // Seed one coffee memory.
    extractionQueue = [[{ text: "User likes coffee" }]];
    await memory.add([{ role: "user", content: "I like coffee" }], { userId: "t1" });

    // Orthogonal topic: cosine similarity to the stored memory is 0.
    extractionQueue = [[]];
    await memory.add([{ role: "user", content: "The sky is blue" }], { userId: "t1" });

    expect(promptCapture.lastUserPrompt).toContain("User likes coffee");
  });

  it("with a similarity threshold the dissimilar memory is filtered out", async () => {
    const memory = createMemory({ dedupSearchThreshold: 0.5 });

    extractionQueue = [[{ text: "User likes coffee" }]];
    await memory.add([{ role: "user", content: "I like coffee" }], { userId: "t2" });

    extractionQueue = [[]];
    await memory.add([{ role: "user", content: "The sky is blue" }], { userId: "t2" });

    expect(promptCapture.lastUserPrompt).not.toContain("User likes coffee");
  });

  it("with a similarity threshold a similar memory is still shown", async () => {
    const memory = createMemory({ dedupSearchThreshold: 0.5 });

    extractionQueue = [[{ text: "User likes coffee" }]];
    await memory.add([{ role: "user", content: "I like coffee" }], { userId: "t3" });

    extractionQueue = [[]];
    await memory.add([{ role: "user", content: "I really like coffee" }], { userId: "t3" });

    expect(promptCapture.lastUserPrompt).toContain("User likes coffee");
  });
});
