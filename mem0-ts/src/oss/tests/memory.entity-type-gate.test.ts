/**
 * Entity-type merge gate tests (#6529).
 *
 * Ports the Python entity_type merge gate (#5497) to the TS OSS SDK. Entities
 * with the same text but a different entityType must NOT be merged (e.g.
 * "Python" the language vs the snake); a new entity is inserted instead. When
 * either side lacks a type the merge is still allowed (backward compat) and a
 * missing stored type is backfilled from the new entity.
 *
 * Covers both merge sites in memory/index.ts:
 *   - _linkEntitiesForMemory (update() path)
 *   - Phase 7c/7d batch path (add() path)
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";
import type { MemoryConfig } from "../src/types";

jest.setTimeout(15000);

// Mock Google modules to prevent @google/genai crash in CI.
jest.mock("../src/embeddings/google", () => ({
  GoogleEmbedder: jest.fn(),
}));
jest.mock("../src/llms/google", () => ({
  GoogleLLM: jest.fn(),
}));

// Deterministic entity extraction so tests control text + type exactly.
jest.mock("../src/utils/entity_extraction", () => {
  const actual = jest.requireActual("../src/utils/entity_extraction");
  return {
    ...actual,
    extractEntities: jest.fn(),
    extractEntitiesBatch: jest.fn(),
  };
});
import {
  extractEntities,
  extractEntitiesBatch,
} from "../src/utils/entity_extraction";

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

// LLM mock: echoes the `## New Messages` section back as a single extracted
// memory so add() produces exactly one ADD record and reaches Phase 7.
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
          const extracted = newMsgMatch
            ? newMsgMatch[1].trim()
            : "extracted fact";
          return JSON.stringify({
            memory: [{ id: "0", text: extracted, attributed_to: "user" }],
          });
        },
      ),
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
        collectionName: `test-etgate-${Date.now()}-${Math.random()}`,
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

/**
 * Build a mock entity store where the given payload rows already exist. `list`
 * feeds the exact-match lookup (_existingEntitiesByText); update/insert are
 * spies so tests can assert which path ran.
 */
function makeEntityStore(existingRows: Array<{ id: string; payload: any }>) {
  return {
    list: jest.fn().mockResolvedValue([existingRows]),
    search: jest.fn().mockResolvedValue([]),
    update: jest.fn().mockResolvedValue(undefined),
    insert: jest.fn().mockResolvedValue(undefined),
    initialize: jest.fn().mockResolvedValue(undefined),
  };
}

describe("Entity-type merge gate (#6529)", () => {
  let warnSpy: jest.SpyInstance;

  beforeEach(() => {
    warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    warnSpy.mockRestore();
    jest.clearAllMocks();
  });

  describe("_linkEntitiesForMemory (update path)", () => {
    async function run(
      newEntity: { type: string; text: string },
      storedPayload: Record<string, any>,
    ) {
      (extractEntities as jest.Mock).mockReturnValue([newEntity]);
      const memory = createMemory();
      const m = memory as any;
      await m._ensureInitialized();
      const store = makeEntityStore([
        { id: "entity-1", payload: storedPayload },
      ]);
      m._entityStore = store;
      await m._linkEntitiesForMemory("mem-B", "irrelevant", {
        user_id: "u1",
      });
      await memory.reset();
      return store;
    }

    it("merges when stored and new entityType match", async () => {
      const store = await run(
        { type: "language", text: "python" },
        { data: "python", entityType: "language", linkedMemoryIds: ["mem-A"] },
      );
      expect(store.update).toHaveBeenCalledTimes(1);
      expect(store.insert).not.toHaveBeenCalled();
    });

    it("inserts a new entity when entityType differs", async () => {
      const store = await run(
        { type: "animal", text: "python" },
        { data: "python", entityType: "language", linkedMemoryIds: ["mem-A"] },
      );
      expect(store.update).not.toHaveBeenCalled();
      expect(store.insert).toHaveBeenCalledTimes(1);
      const insertedPayload = store.insert.mock.calls[0][2][0];
      expect(insertedPayload.entityType).toBe("animal");
      expect(insertedPayload.data).toBe("python");
      expect(warnSpy).toHaveBeenCalled();
    });

    it("still merges (and backfills type) when the stored entity has no type", async () => {
      const store = await run(
        { type: "language", text: "python" },
        { data: "python", linkedMemoryIds: ["mem-A"] },
      );
      expect(store.update).toHaveBeenCalledTimes(1);
      expect(store.insert).not.toHaveBeenCalled();
      const updatedPayload = store.update.mock.calls[0][2];
      expect(updatedPayload.entityType).toBe("language");
    });

    it("still merges when the new entity has no type", async () => {
      const store = await run(
        { type: "", text: "python" },
        { data: "python", entityType: "language", linkedMemoryIds: ["mem-A"] },
      );
      expect(store.update).toHaveBeenCalledTimes(1);
      expect(store.insert).not.toHaveBeenCalled();
    });
  });

  describe("Phase 7c/7d batch path (add path)", () => {
    it("inserts a new entity when entityType differs in the batch path", async () => {
      (extractEntitiesBatch as jest.Mock).mockReturnValue([
        [{ type: "animal", text: "python" }],
      ]);
      const memory = createMemory();
      const m = memory as any;
      await m._ensureInitialized();
      const store = makeEntityStore([
        {
          id: "entity-1",
          payload: {
            data: "python",
            entityType: "language",
            linkedMemoryIds: ["mem-A"],
          },
        },
      ]);
      m._entityStore = store;

      await memory.add("python the animal", { userId: "u1" });

      expect(store.update).not.toHaveBeenCalled();
      expect(store.insert).toHaveBeenCalledTimes(1);
      const insertedPayload = store.insert.mock.calls[0][2][0];
      expect(insertedPayload.entityType).toBe("animal");
      expect(warnSpy).toHaveBeenCalled();
      await memory.reset();
    });

    it("merges in the batch path when entityType matches", async () => {
      (extractEntitiesBatch as jest.Mock).mockReturnValue([
        [{ type: "language", text: "python" }],
      ]);
      const memory = createMemory();
      const m = memory as any;
      await m._ensureInitialized();
      const store = makeEntityStore([
        {
          id: "entity-1",
          payload: {
            data: "python",
            entityType: "language",
            linkedMemoryIds: ["mem-A"],
          },
        },
      ]);
      m._entityStore = store;

      await memory.add("python the language", { userId: "u1" });

      expect(store.update).toHaveBeenCalledTimes(1);
      expect(store.insert).not.toHaveBeenCalled();
      await memory.reset();
    });

    it("backfills the missing stored type in the batch path", async () => {
      (extractEntitiesBatch as jest.Mock).mockReturnValue([
        [{ type: "language", text: "python" }],
      ]);
      const memory = createMemory();
      const m = memory as any;
      await m._ensureInitialized();
      const store = makeEntityStore([
        {
          id: "entity-1",
          payload: { data: "python", linkedMemoryIds: ["mem-A"] },
        },
      ]);
      m._entityStore = store;

      await memory.add("python the language", { userId: "u1" });

      expect(store.update).toHaveBeenCalledTimes(1);
      expect(store.insert).not.toHaveBeenCalled();
      const updatedPayload = store.update.mock.calls[0][2];
      expect(updatedPayload.entityType).toBe("language");
      await memory.reset();
    });
  });
});
