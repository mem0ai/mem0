/**
 * OSS Memory unit tests — add() with inference, without inference, filter validation, metadata.
 * Content-based LLM mock: system-prompt calls → facts, user-only calls → memory actions.
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import type { MemoryConfig, MemoryItem, SearchResult } from "../src/types";

jest.setTimeout(15000);

jest.mock("../src/utils/factory", () => {
  const { MemoryVectorStore } = jest.requireActual(
    "../src/vector_stores/memory",
  );
  const { MemoryHistoryManager } = jest.requireActual(
    "../src/storage/MemoryHistoryManager",
  );
  const testEmbedding = new Array(1536).fill(0.1);

  class MockEmbedder {
    embeddingDims = 1536;

    async embed(): Promise<number[]> {
      return testEmbedding;
    }

    async embedBatch(texts: string[]): Promise<number[][]> {
      return texts.map(() => testEmbedding);
    }
  }

  class MockLLM {
    async generateResponse(messages: Array<{ role: string; content: string }>) {
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
    }
  }

  return {
    __esModule: true,
    EmbedderFactory: {
      create: jest.fn(() => new MockEmbedder()),
    },
    LLMFactory: {
      create: jest.fn(() => new MockLLM()),
    },
    VectorStoreFactory: {
      create: jest.fn((provider: string, config: any) => {
        if (provider.toLowerCase() !== "memory") {
          throw new Error(
            `Unsupported vector store provider in test: ${provider}`,
          );
        }
        return new MemoryVectorStore(config);
      }),
    },
    HistoryManagerFactory: {
      create: jest.fn(() => new MemoryHistoryManager()),
    },
    RerankerFactory: {
      create: jest.fn(() => {
        throw new Error("RerankerFactory is not used in memory.add.test.ts");
      }),
    },
  };
});

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

  test("does not allow metadata to set identity scope", async () => {
    const result: SearchResult = await memory.add("I am a software engineer", {
      userId: "u1",
      metadata: {
        agent_id: "other",
        agentId: "other-camel",
        run_id: "other-run",
        runId: "other-run-camel",
        actor_id: "x",
        source: "issue-6371",
        nested: { preserved: true },
      },
    });
    const stored: MemoryItem | null = await memory.get(result.results[0].id);

    expect(stored).toEqual(
      expect.objectContaining({
        user_id: "u1",
        metadata: expect.objectContaining({
          source: "issue-6371",
          nested: { preserved: true },
        }),
      }),
    );
    expect(stored).not.toHaveProperty("agent_id");
    expect(stored).not.toHaveProperty("run_id");
    expect(stored!.metadata).not.toHaveProperty("agent_id");
    expect(stored!.metadata).not.toHaveProperty("agentId");
    expect(stored!.metadata).not.toHaveProperty("run_id");
    expect(stored!.metadata).not.toHaveProperty("runId");
    expect(stored!.metadata).not.toHaveProperty("actor_id");
  });

  test.each([
    ["userId", { userId: "u1" }, true, "user_id", "u1"],
    ["agentId", { agentId: "a1" }, false, "agent_id", "a1"],
    ["runId", { runId: "r1" }, true, "run_id", "r1"],
  ] as const)(
    "preserves typed %s scope while stripping conflicting metadata identities",
    async (_mode, scope, infer, canonicalKey, canonicalValue) => {
      const result: SearchResult = await memory.add("scoped content", {
        ...scope,
        infer,
        metadata: {
          user_id: "metadata-user",
          userId: "metadata-user-camel",
          agent_id: "metadata-agent",
          agentId: "metadata-agent-camel",
          run_id: "metadata-run",
          runId: "metadata-run-camel",
          actor_id: "metadata-actor",
          ordinary: "preserved",
        },
      });
      const stored: MemoryItem | null = await memory.get(result.results[0].id);

      expect(stored).toHaveProperty(canonicalKey, canonicalValue);
      for (const key of ["user_id", "agent_id", "run_id"]) {
        if (key !== canonicalKey) {
          expect(stored).not.toHaveProperty(key);
        }
      }
      expect(stored!.metadata).toEqual(
        expect.objectContaining({ ordinary: "preserved" }),
      );
      for (const key of [
        "user_id",
        "userId",
        "agent_id",
        "agentId",
        "run_id",
        "runId",
        "actor_id",
      ]) {
        expect(stored!.metadata).not.toHaveProperty(key);
      }
    },
  );

  test.each([
    [true, "user_id", "filter-user"],
    [false, "user_id", "filter-user"],
    [false, "agent_id", "filter-agent"],
    [false, "run_id", "filter-run"],
  ] as const)(
    "preserves infer=%s %s filters scope after sanitization",
    async (infer, filterKey, filterValue) => {
      const result: SearchResult = await memory.add("filter-scoped content", {
        filters: { [filterKey]: filterValue },
        infer,
        metadata: {
          user_id: "metadata-user",
          userId: "metadata-user-camel",
          agent_id: "metadata-agent",
          agentId: "metadata-agent-camel",
          run_id: "metadata-run",
          runId: "metadata-run-camel",
          actor_id: "metadata-actor",
          ordinary: "preserved",
        },
      });
      const stored: MemoryItem | null = await memory.get(result.results[0].id);

      expect(stored).toHaveProperty(filterKey, filterValue);
      for (const key of ["user_id", "agent_id", "run_id"]) {
        if (key !== filterKey) {
          expect(stored).not.toHaveProperty(key);
        }
      }
      expect(stored!.metadata).toEqual(
        expect.objectContaining({ ordinary: "preserved" }),
      );
      for (const key of [
        "user_id",
        "userId",
        "agent_id",
        "agentId",
        "run_id",
        "runId",
        "actor_id",
      ]) {
        expect(stored!.metadata).not.toHaveProperty(key);
      }
    },
  );

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
});
