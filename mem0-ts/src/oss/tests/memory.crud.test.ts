/**
 * OSS Memory unit tests — get, update, delete, deleteAll, getAll, search, history.
 * Content-based LLM mock. Tests verify real behavior, not mock echoes.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import type { MemoryItem, SearchResult } from "../src/types";
import { logger } from "../src/utils/logger";

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
    const result = await memory.update(id, { text: "Updated" });
    expect(result.message).toBe("Memory updated successfully!");
  });

  test("persists the updated text", async () => {
    const addResult: SearchResult = await memory.add("Before update", {
      userId,
      infer: false,
    });
    const id = addResult.results[0].id;
    await memory.update(id, { text: "After update" });
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

    await memory.update(id, { text: "New text" });
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
    await memory.update(id, { text: "Completely different text" });
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.hash).not.toBe(before!.hash);
  });

  test("preserves custom metadata fields after update", async () => {
    const addResult: SearchResult = await memory.add("Original text", {
      userId,
      metadata: { category: "hobbies", priority: "high" },
      infer: false,
    });
    const id = addResult.results[0].id;
    await memory.update(id, { text: "Updated text" });
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.memory).toBe("Updated text");
    expect(after!.metadata).toEqual(
      expect.objectContaining({ category: "hobbies", priority: "high" }),
    );
  });
});

// ─── update() options: text / data / metadata / expirationDate ───

describe("Memory - update() options", () => {
  let memory: Memory;
  let warnSpy: jest.SpyInstance;
  const userId = `update_options_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  beforeEach(() => {
    warnSpy = jest.spyOn(logger, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    warnSpy.mockRestore();
  });

  afterAll(async () => {
    await memory.reset();
  });

  async function seed(text: string): Promise<string> {
    const addResult: SearchResult = await memory.add(text, {
      userId,
      infer: false,
    });
    return addResult.results[0].id;
  }

  test("accepts an options object with text, without warning", async () => {
    const id = await seed("Options before");
    await memory.update(id, { text: "Options after" });
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.memory).toBe("Options after");
    expect(warnSpy).not.toHaveBeenCalled();
  });

  test("accepts a bare text string, as on main", async () => {
    const id = await seed("Bare before");
    await memory.update(id, "Bare after");
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.memory).toBe("Bare after");
  });

  test("accepts the deprecated data alias and warns", async () => {
    const id = await seed("Alias before");
    await memory.update(id, { data: "Alias after" });
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.memory).toBe("Alias after");
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining("deprecated"));
  });

  // An empty `text` is content, so it must beat `data`. Guards against `||=`,
  // which would treat "" as absent and store the `data` value instead.
  test("text wins over data, even when text is empty", async () => {
    const id = await seed("Both before");
    await memory.update(id, { text: "", data: "From data" });
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.memory).toBe("");
  });

  // Same trap on the guard: "" must not read as "no field provided".
  test("an empty bare string is content, not a missing argument", async () => {
    const id = await seed("Empty bare");
    await memory.update(id, "");
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.memory).toBe("");
  });

  test("updates metadata without touching the stored text", async () => {
    const id = await seed("Metadata only");
    await memory.update(id, { metadata: { category: "solo" } });
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.memory).toBe("Metadata only");
    expect(after!.metadata).toEqual(
      expect.objectContaining({ category: "solo" }),
    );
  });

  test("sets an expiration date without touching the stored text", async () => {
    const id = await seed("Expiry only");
    await memory.update(id, { expirationDate: "2099-12-31" });
    const after: MemoryItem | null = await memory.get(id);
    expect(after!.memory).toBe("Expiry only");
    expect(after!.metadata).toEqual(
      expect.objectContaining({ expiration_date: "2099-12-31" }),
    );
  });

  // Python raises on `data=None` / `metadata=None`, so loose `== null` is the
  // right check for both. `{}` is a real value and must not raise.
  test.each([{}, { data: null }, { metadata: null }])(
    "throws when %p provides nothing updatable",
    async (options) => {
      const id = await seed("Nothing to update");
      await expect(memory.update(id, options as any)).rejects.toThrow(
        "At least one of text, metadata, or expirationDate must be provided.",
      );
      expect(warnSpy).not.toHaveBeenCalled();
    },
  );

  test("accepts empty metadata as an updatable field", async () => {
    const id = await seed("Empty metadata");
    await expect(memory.update(id, { metadata: {} })).resolves.toEqual({
      message: "Memory updated successfully!",
    });
  });
});

// ─── expiration date parsing ─────────────────────────────

describe("Memory - expiration date parsing", () => {
  let memory: Memory;
  const userId = `expiry_parse_test_${Date.now()}`;

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  // `new Date(...)` accepts all of these; Python's date.fromisoformat rejects
  // them. The first two die to the format regex, the last two only to the
  // UTC component round-trip: they match YYYY-MM-DD but are not real days.
  const rejected = [
    "12/31/2099", // also shifts a day west of UTC
    "2099-12-31T23:00:00",
    "2099-02-30", // rolls over to 2099-03-02
    "2100-02-29", // 2100 is not a leap year
  ];

  test.each(rejected)("add() rejects %p", async (value) => {
    await expect(
      memory.add("Bad expiry", { userId, infer: false, expirationDate: value }),
    ).rejects.toThrow("YYYY-MM-DD");
  });

  // add() and update() share normalizeExpirationDate(); this checks the wiring.
  test("update() rejects a malformed expiration date", async () => {
    const addResult: SearchResult = await memory.add("Good", {
      userId,
      infer: false,
    });
    await expect(
      memory.update(addResult.results[0].id, { expirationDate: "12/31/2099" }),
    ).rejects.toThrow("YYYY-MM-DD");
  });

  // "2096-02-29" is a real leap day: it must survive the component check.
  test.each(["2099-12-31", "2096-02-29"])(
    "stores %p verbatim",
    async (value) => {
      const addResult: SearchResult = await memory.add("Good expiry", {
        userId,
        infer: false,
        expirationDate: value,
      });
      const item: MemoryItem | null = await memory.get(addResult.results[0].id);
      expect(item!.metadata!.expiration_date).toBe(value);
    },
  );
});

// ─── expired memories are hidden on read ─────────────────

describe("Memory - expired memories", () => {
  let memory: Memory;
  const userId = `expired_test_${Date.now()}`;
  const today = new Date().toISOString().slice(0, 10);

  beforeAll(async () => {
    memory = createMemory();
  });

  afterAll(async () => {
    await memory.reset();
  });

  async function seed(text: string, expirationDate?: string): Promise<string> {
    const addResult: SearchResult = await memory.add(text, {
      userId,
      infer: false,
      ...(expirationDate ? { expirationDate } : {}),
    });
    return addResult.results[0].id;
  }

  async function seedLiveAndDead(scopedUser: string): Promise<void> {
    await memory.add("Live memory", { userId: scopedUser, infer: false });
    await memory.add("Dead memory", {
      userId: scopedUser,
      infer: false,
      expirationDate: "2020-01-01",
    });
  }

  test("getAll() hides expired memories unless showExpired", async () => {
    const scopedUser = `${userId}_getall`;
    await seedLiveAndDead(scopedUser);
    const filters = { user_id: scopedUser };

    const hidden: SearchResult = await memory.getAll({ filters });
    expect(hidden.results.map((r) => r.memory)).toEqual(["Live memory"]);

    const shown: SearchResult = await memory.getAll({
      filters,
      showExpired: true,
    });
    expect(shown.results.map((r) => r.memory).sort()).toEqual([
      "Dead memory",
      "Live memory",
    ]);
  });

  test("search() hides expired memories unless showExpired", async () => {
    const scopedUser = `${userId}_search`;
    await seedLiveAndDead(scopedUser);
    const filters = { user_id: scopedUser };

    const hidden: SearchResult = await memory.search("memory", { filters });
    expect(hidden.results.map((r) => r.memory)).toEqual(["Live memory"]);

    const shown: SearchResult = await memory.search("memory", {
      filters,
      showExpired: true,
    });
    expect(shown.results.map((r) => r.memory).sort()).toEqual([
      "Dead memory",
      "Live memory",
    ]);
  });

  test("a memory expiring today is not yet expired", async () => {
    const scopedUser = `${userId}_today`;
    await memory.add("Expires today", {
      userId: scopedUser,
      infer: false,
      expirationDate: today,
    });
    const result: SearchResult = await memory.getAll({
      filters: { user_id: scopedUser },
    });
    expect(result.results).toHaveLength(1);
  });

  test("get() still returns an expired memory by ID", async () => {
    const id = await seed("Fetch by id", "2020-01-01");
    const item: MemoryItem | null = await memory.get(id);
    expect(item).not.toBeNull();
    expect(item!.memory).toBe("Fetch by id");
  });

  test("clearing the expiration date makes a memory visible again", async () => {
    const scopedUser = `${userId}_revive`;
    const addResult: SearchResult = await memory.add("Revived", {
      userId: scopedUser,
      infer: false,
      expirationDate: "2020-01-01",
    });
    const id = addResult.results[0].id;

    const before: SearchResult = await memory.getAll({
      filters: { user_id: scopedUser },
    });
    expect(before.results).toHaveLength(0);

    await memory.update(id, { expirationDate: null });

    const after: SearchResult = await memory.getAll({
      filters: { user_id: scopedUser },
    });
    expect(after.results.map((r) => r.memory)).toEqual(["Revived"]);
  });

  test("getAll() still fills topK when expired memories are present", async () => {
    const scopedUser = `${userId}_topk`;
    for (let i = 0; i < 3; i++) {
      await memory.add(`Dead ${i}`, {
        userId: scopedUser,
        infer: false,
        expirationDate: "2020-01-01",
      });
    }
    for (let i = 0; i < 3; i++) {
      await memory.add(`Live ${i}`, { userId: scopedUser, infer: false });
    }

    const result: SearchResult = await memory.getAll({
      filters: { user_id: scopedUser },
      topK: 3,
    });
    expect(result.results).toHaveLength(3);
    expect(result.results.every((r) => r.memory!.startsWith("Live"))).toBe(
      true,
    );
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

// ─── attributedTo (#5666) ────────────────────────────────

describe("Memory - attributedTo round-trip (#5666)", () => {
  let memory: Memory;
  const userId = `attributed_test_${Date.now()}`;
  let id: string;

  beforeAll(async () => {
    memory = createMemory();
    // The mocked LLM tags every extracted fact with attributed_to: "user".
    const addResult: SearchResult = await memory.add("I love AI", { userId });
    id = addResult.results[0].id;
  });

  afterAll(async () => {
    await memory.reset();
  });

  test("get() surfaces attributedTo", async () => {
    const item: MemoryItem | null = await memory.get(id);
    expect(item!.attributedTo).toBe("user");
  });

  test("getAll() surfaces attributedTo", async () => {
    const result: SearchResult = await memory.getAll({
      filters: { user_id: userId },
    });
    expect(result.results[0].attributedTo).toBe("user");
  });

  test("search() surfaces attributedTo", async () => {
    const result: SearchResult = await memory.search("AI", {
      filters: { user_id: userId },
    });
    expect(result.results.length).toBeGreaterThan(0);
    expect(result.results[0].attributedTo).toBe("user");
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
    await memory.update(id, { text: "After" });
    const history = await memory.history(id);
    expect(history.length).toBeGreaterThanOrEqual(2);
  });

  test("returns empty array for non-existent memory ID", async () => {
    const history = await memory.history("nonexistent-id");
    expect(history).toHaveLength(0);
  });
});
