/**
 * OSS Memory unit tests — get, update, delete, deleteAll, getAll, search, history.
 * Content-based LLM mock. Tests verify real behavior, not mock echoes.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import type { MemoryItem, SearchResult } from "../src/types";

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
          // V3 pipeline: single LLM call with additive extraction prompt.
          // Extract the user input from the prompt to produce unique memories.
          const userMsg = messages.find((m) => m.role === "user");
          const content = userMsg?.content ?? "";
          // Pull the text between "## New Messages" and the next "##"
          const newMsgMatch = content.match(
            /## New Messages\n([\s\S]*?)(?=\n##|$)/,
          );
          const extracted = newMsgMatch ? newMsgMatch[1].trim() : "stored fact";
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
        collectionName: `test-crud-${Date.now()}-${Math.random()}`,
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

// ─── get() ───────────────────────────────────────────────

describe("Memory - get()", () => {
  let memory: Memory;
  const userId = `get_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("returns the memory matching the ID from add()", async () => {
    const addResult: SearchResult = await memory.add("I love AI", {
      userId,
    });
    const id = addResult.results[0].id;
    const item: MemoryItem | null = await memory.get(id);
    expect(item).not.toBeNull();
    expect(item!.id).toBe(id);
  });

  test("returns a string for the memory field", async () => {
    const addResult: SearchResult = await memory.add("Testing get", {
      userId,
    });
    const item: MemoryItem | null = await memory.get(addResult.results[0].id);
    expect(typeof item!.memory).toBe("string");
  });

  test("returns null for non-existent ID", async () => {
    const item = await memory.get("nonexistent-uuid-12345");
    expect(item).toBeNull();
  });

  test("returns hash and createdAt on stored memory", async () => {
    const addResult: SearchResult = await memory.add("Hash test", {
      userId,
    });
    const item: MemoryItem | null = await memory.get(addResult.results[0].id);
    expect(typeof item!.hash).toBe("string");
    expect(item!.createdAt).toBeDefined();
    expect(new Date(item!.createdAt!).toString()).not.toBe("Invalid Date");
  });
});

// ─── update() ────────────────────────────────────────────

describe("Memory - update()", () => {
  let memory: Memory;
  const userId = `update_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  // Use infer: false for update tests — bypasses LLM, gives us a stable ID
  test("returns success message", async () => {
    const addResult: SearchResult = await memory.add("Original", {
      userId,
      infer: false,
    });
    const id = addResult.results[0].id;
    const result = await memory.update(id, "Updated");
    expect(result.message).toBe("Memory updated successfully!");
  });

  test("persists the updated text", async () => {
    const addResult: SearchResult = await memory.add("Before update", {
      userId,
      infer: false,
    });
    const id = addResult.results[0].id;
    await memory.update(id, "After update");
    const item: MemoryItem | null = await memory.get(id);
    expect(item!.memory).toBe("After update");
  });

  test("preserves createdAt and sets updatedAt", async () => {
    const addResult: SearchResult = await memory.add("Timestamp test", {
      userId,
      infer: false,
    });
    const id = addResult.results[0].id;
    const before: MemoryItem | null = await memory.get(id);
    const originalCreatedAt = before!.createdAt;

    await memory.update(id, "New text");
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.createdAt).toBe(originalCreatedAt);
    expect(after!.updatedAt).toBeDefined();
  });

  test("updates the hash", async () => {
    const addResult: SearchResult = await memory.add("Hash change", {
      userId,
      infer: false,
    });
    const id = addResult.results[0].id;
    const before: MemoryItem | null = await memory.get(id);
    await memory.update(id, "Completely different text");
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.hash).not.toBe(before!.hash);
  });
});

// ─── delete() ────────────────────────────────────────────

describe("Memory - delete()", () => {
  let memory: Memory;
  const userId = `delete_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("returns success message", async () => {
    const addResult: SearchResult = await memory.add("Delete me", {
      userId,
      infer: false,
    });
    const result = await memory.delete(addResult.results[0].id);
    expect(result.message).toBe("Memory deleted successfully!");
  });

  test("get() returns null after deletion", async () => {
    const addResult: SearchResult = await memory.add("Temporary", {
      userId,
      infer: false,
    });
    const id = addResult.results[0].id;
    await memory.delete(id);
    expect(await memory.get(id)).toBeNull();
  });
});

// ─── deleteAll() ─────────────────────────────────────────

describe("Memory - deleteAll()", () => {
  let memory: Memory;
  const userId = `deleteall_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("removes all memories for the user and returns success", async () => {
    await memory.add("Fact A", { userId });
    await memory.add("Fact B", { userId });
    const result = await memory.deleteAll({ userId });
    expect(result.message).toBe("Memories deleted successfully!");
    const remaining: SearchResult = await memory.getAll({
      filters: { user_id: userId },
    });
    expect(remaining.results).toHaveLength(0);
  });

  test("throws when no filter is provided", async () => {
    await expect(memory.deleteAll({} as any)).rejects.toThrow(
      "At least one filter is required to delete all memories",
    );
  });
});

// ─── getAll() ────────────────────────────────────────────

describe("Memory - getAll()", () => {
  let memory: Memory;
  const userId = `getall_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("returns all stored memories for the user", async () => {
    await memory.add("First", { userId });
    await memory.add("Second", { userId });
    const result: SearchResult = await memory.getAll({
      filters: { user_id: userId },
    });
    expect(Array.isArray(result.results)).toBe(true);
    expect(result.results.length).toBeGreaterThanOrEqual(2);
  });

  test("each result has id and memory fields", async () => {
    const result: SearchResult = await memory.getAll({
      filters: { user_id: userId },
    });
    for (const item of result.results) {
      expect(item.id).toBeDefined();
      expect(typeof item.memory).toBe("string");
    }
  });

  test("returns empty array when no memories exist", async () => {
    const result: SearchResult = await memory.getAll({
      filters: { user_id: "no_such_user" },
    });
    expect(result.results).toHaveLength(0);
  });
});

// ─── search() ────────────────────────────────────────────

describe("Memory - search()", () => {
  let memory: Memory;
  const userId = `search_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
    await memory.add("I love TypeScript", { userId });
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("returns SearchResult with results array", async () => {
    const result: SearchResult = await memory.search("TypeScript", {
      filters: { user_id: userId },
    });
    expect(Array.isArray(result.results)).toBe(true);
  });

  test("returns results with score field", async () => {
    const result: SearchResult = await memory.search("content", {
      filters: { user_id: userId },
    });
    if (result.results.length > 0) {
      expect(typeof result.results[0].score).toBe("number");
    }
  });

  test("throws when no userId/agentId/runId provided", async () => {
    await expect(memory.search("query", {} as any)).rejects.toThrow(
      "filters must contain at least one of: user_id, agent_id, run_id",
    );
  });

  test("returns empty results for user with no memories", async () => {
    const result: SearchResult = await memory.search("query", {
      filters: { user_id: "empty_user" },
    });
    expect(result.results).toHaveLength(0);
  });
});

// ─── history() ───────────────────────────────────────────

describe("Memory - history()", () => {
  let memory: Memory;
  const userId = `history_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("records ADD event after add()", async () => {
    const addResult: SearchResult = await memory.add("New fact", {
      userId,
    });
    const history = await memory.history(addResult.results[0].id);
    expect(Array.isArray(history)).toBe(true);
    expect(history.length).toBeGreaterThan(0);
  });

  test("records additional entry after update()", async () => {
    const addResult: SearchResult = await memory.add("Before", {
      userId,
    });
    const id = addResult.results[0].id;
    await memory.update(id, "After");
    const history = await memory.history(id);
    expect(history.length).toBeGreaterThanOrEqual(2);
  });

  test("returns empty array for non-existent memory ID", async () => {
    const history = await memory.history("nonexistent-id");
    expect(history).toHaveLength(0);
  });
});
