/// <reference types="jest" />
import { Memory } from "../src/memory";
import { MemoryItem, SearchResult } from "../src/types";

jest.setTimeout(30000);

// Mock LLM and embedder so tests run without API keys.
//
// IMPORTANT: Memory.add() calls generateResponse exactly 2 times per invocation:
//   1st call (odd): fact extraction → returns { facts: [...] }
//   2nd call (even): memory update decision → returns { memory: [{ event: "ADD", text, ... }] }
// If Memory's internal call sequence changes, this mock must be updated.
let llmCallCount = 0;
jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest.fn().mockImplementation(() => {
      llmCallCount++;
      if (llmCallCount % 2 === 1) {
        return JSON.stringify({ facts: ["John is a software engineer"] });
      }
      return JSON.stringify({
        memory: [
          {
            id: "new",
            event: "ADD",
            text: "John is a software engineer",
            old_memory: "",
            new_memory: "John is a software engineer",
          },
        ],
      });
    }),
  })),
}));

jest.mock("../src/embeddings/openai", () => ({
  OpenAIEmbedder: jest.fn().mockImplementation(() => ({
    embed: jest.fn().mockResolvedValue(new Array(1536).fill(0.1)),
    embeddingDims: 1536,
  })),
}));

describe("Memory Class", () => {
  let memory: Memory;
  const userId =
    Math.random().toString(36).substring(2, 15) +
    Math.random().toString(36).substring(2, 15);

  beforeEach(async () => {
    llmCallCount = 0;
    memory = new Memory({
      version: "v1.1",
      embedder: {
        provider: "openai",
        config: { apiKey: "test-key", model: "text-embedding-3-small" },
      },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test-memories", dimension: 1536 },
      },
      llm: {
        provider: "openai",
        config: { apiKey: "test-key", model: "gpt-4-turbo-preview" },
      },
      historyDbPath: ":memory:",
    });
    await memory.reset();
  });

  afterEach(async () => {
    await memory.reset();
  });

  describe("add() single memory", () => {
    let result: SearchResult;

    beforeEach(async () => {
      result = (await memory.add(
        "Hi, my name is John and I am a software engineer.",
        { userId },
      )) as SearchResult;
    });

    it("returns a defined result", () => {
      expect(result).toBeDefined();
    });

    it("returns results array", () => {
      expect(Array.isArray(result.results)).toBe(true);
    });

    it("returns at least one result", () => {
      expect(result.results.length).toBeGreaterThan(0);
    });

    it("returns result with an id", () => {
      expect(result.results[0]?.id).toBeDefined();
    });
  });

  describe("add() multiple messages", () => {
    let result: SearchResult;

    beforeEach(async () => {
      const messages = [
        { role: "user", content: "What is your favorite city?" },
        { role: "assistant", content: "I love Paris, it is my favorite city." },
      ];
      result = (await memory.add(messages, { userId })) as SearchResult;
    });

    it("returns results array", () => {
      expect(Array.isArray(result.results)).toBe(true);
    });

    it("returns at least one result", () => {
      expect(result.results.length).toBeGreaterThan(0);
    });
  });

  describe("get() single memory", () => {
    let memoryItem: MemoryItem;
    let memoryId: string;

    beforeEach(async () => {
      const addResult = (await memory.add(
        "I am a big advocate of using AI to make the world a better place",
        { userId },
      )) as SearchResult;
      memoryId = addResult.results[0].id;
      memoryItem = (await memory.get(memoryId)) as MemoryItem;
    });

    it("returns the correct id", () => {
      expect(memoryItem.id).toBe(memoryId);
    });

    it("returns a string memory", () => {
      expect(typeof memoryItem.memory).toBe("string");
    });
  });

  describe("update() memory", () => {
    let memoryId: string;

    beforeEach(async () => {
      const addResult = (await memory.add(
        "I love speaking foreign languages especially Spanish",
        { userId },
      )) as SearchResult;
      memoryId = addResult.results[0].id;
    });

    it("returns success message", async () => {
      const result = await memory.update(memoryId, "Updated content");
      expect(result.message).toBe("Memory updated successfully!");
    });

    it("persists the updated content", async () => {
      await memory.update(memoryId, "Updated content");
      const updated = (await memory.get(memoryId)) as MemoryItem;
      expect(updated.memory).toBe("Updated content");
    });
  });

  describe("getAll() memories for user", () => {
    let result: SearchResult;

    beforeEach(async () => {
      await memory.add("I love visiting new places in the winters", { userId });
      await memory.add("I like to rule the world", { userId });
      result = (await memory.getAll({ userId })) as SearchResult;
    });

    it("returns results array", () => {
      expect(Array.isArray(result.results)).toBe(true);
    });

    it("returns at least two results", () => {
      expect(result.results.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe("search() memories", () => {
    let result: SearchResult;

    beforeEach(async () => {
      await memory.add("I love programming in Python", { userId });
      await memory.add("JavaScript is my favorite language", { userId });
      result = (await memory.search("What programming languages do I know?", {
        userId,
      })) as SearchResult;
    });

    it("returns results array", () => {
      expect(Array.isArray(result.results)).toBe(true);
    });

    it("returns at least one result", () => {
      expect(result.results.length).toBeGreaterThan(0);
    });
  });

  describe("history() of a memory", () => {
    let history: unknown[];

    beforeEach(async () => {
      const addResult = (await memory.add("I like swimming in warm water", {
        userId,
      })) as SearchResult;
      const memoryId = addResult.results[0].id;
      await memory.update(memoryId, "Updated content");
      history = await memory.history(memoryId);
    });

    it("returns an array", () => {
      expect(Array.isArray(history)).toBe(true);
    });

    it("returns at least one entry", () => {
      expect(history.length).toBeGreaterThan(0);
    });
  });

  describe("delete() a memory", () => {
    it("returns null after deletion", async () => {
      const addResult = (await memory.add("I love to drink vodka in summers", {
        userId,
      })) as SearchResult;
      const memoryId = addResult.results[0].id;
      await memory.delete(memoryId);
      const result = await memory.get(memoryId);
      expect(result).toBeNull();
    });
  });

  describe("Memory with Custom Configuration", () => {
    let customMemory: Memory;

    beforeEach(() => {
      customMemory = new Memory({
        version: "v1.1",
        embedder: {
          provider: "openai",
          config: { apiKey: "test-key", model: "text-embedding-3-small" },
        },
        vectorStore: {
          provider: "memory",
          config: { collectionName: "test-memories", dimension: 1536 },
        },
        llm: {
          provider: "openai",
          config: { apiKey: "test-key", model: "gpt-4-turbo-preview" },
        },
        historyDbPath: ":memory:",
      });
    });

    afterEach(async () => {
      await customMemory.reset();
    });

    it("add() returns results with custom config", async () => {
      const result = (await customMemory.add("I love programming in Python", {
        userId,
      })) as SearchResult;
      expect(result.results.length).toBeGreaterThan(0);
    });

    it("search() returns results with custom config", async () => {
      await customMemory.add("The weather in London is rainy today", {
        userId,
      });
      await customMemory.add("The temperature in Paris is 25 degrees", {
        userId,
      });
      const result = (await customMemory.search("What is the weather like?", {
        userId,
      })) as SearchResult;
      expect(result.results.length).toBeGreaterThan(0);
    });
  });
});
