/// <reference types="jest" />
import { Memory } from "../src";
import { MemoryItem, SearchResult } from "../src/types";
import dotenv from "dotenv";

dotenv.config();

jest.setTimeout(30000); // Increase timeout to 30 seconds

describe("Memory Class", () => {
  let memory: Memory;
  const userId =
    Math.random().toString(36).substring(2, 15) +
    Math.random().toString(36).substring(2, 15);

  beforeEach(async () => {
    // Initialize with default configuration
    memory = new Memory({
      version: "v1.1",
      embedder: {
        provider: "openai",
        config: {
          apiKey: process.env.OPENAI_API_KEY || "",
          model: "text-embedding-3-small",
        },
      },
      vectorStore: {
        provider: "memory",
        config: {
          collectionName: "test-memories",
          dimension: 1536,
        },
      },
      llm: {
        provider: "openai",
        config: {
          apiKey: process.env.OPENAI_API_KEY || "",
          model: "gpt-4-turbo-preview",
        },
      },
      historyDbPath: ":memory:", // Use in-memory SQLite for tests
    });
    // Reset all memories before each test
    await memory.reset();
  });

  afterEach(async () => {
    // Clean up after each test
    await memory.reset();
  });

  describe("Basic Memory Operations", () => {
    it("should add a single memory", async () => {
      const result = (await memory.add(
        "Hi, my name is John and I am a software engineer.",
        userId,
      )) as SearchResult;

      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
      expect(Array.isArray(result.results)).toBe(true);
      expect(result.results.length).toBeGreaterThan(0);
      expect(result.results[0]?.id).toBeDefined();
    });

    it("should add multiple messages", async () => {
      const messages = [
        { role: "user", content: "What is your favorite city?" },
        { role: "assistant", content: "I love Paris, it is my favorite city." },
      ];

      const result = (await memory.add(messages, userId)) as SearchResult;

      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
      expect(Array.isArray(result.results)).toBe(true);
      expect(result.results.length).toBeGreaterThan(0);
    });

    it("should get a single memory", async () => {
      // First add a memory
      const addResult = (await memory.add(
        "I am a big advocate of using AI to make the world a better place",
        userId,
      )) as SearchResult;

      if (!addResult.results?.[0]?.id) {
        throw new Error("Failed to create test memory");
      }

      const memoryId = addResult.results[0].id;
      const result = (await memory.get(memoryId)) as MemoryItem;

      expect(result).toBeDefined();
      expect(result.id).toBe(memoryId);
      expect(result.memory).toBeDefined();
      expect(typeof result.memory).toBe("string");
    });

    it("should update a memory", async () => {
      // First add a memory
      const addResult = (await memory.add(
        "I love speaking foreign languages especially Spanish",
        userId,
      )) as SearchResult;

      if (!addResult.results?.[0]?.id) {
        throw new Error("Failed to create test memory");
      }

      const memoryId = addResult.results[0].id;
      const updatedContent = "Updated content";
      const result = await memory.update(memoryId, updatedContent);

      expect(result).toBeDefined();
      expect(result.message).toBe("Memory updated successfully!");

      // Verify the update by getting the memory
      const updatedMemory = (await memory.get(memoryId)) as MemoryItem;
      expect(updatedMemory.memory).toBe(updatedContent);
    });

    it("should get all memories for a user", async () => {
      // Add a few memories
      await memory.add("I love visiting new places in the winters", userId);
      await memory.add("I like to rule the world", userId);

      const result = (await memory.getAll(userId)) as SearchResult;

      expect(result).toBeDefined();
      expect(Array.isArray(result.results)).toBe(true);
      expect(result.results.length).toBeGreaterThanOrEqual(2);
    });

    it("should search memories", async () => {
      // Add some test memories
      await memory.add("I love programming in Python", userId);
      await memory.add("JavaScript is my favorite language", userId);

      const result = (await memory.search(
        "What programming languages do I know?",
        userId,
      )) as SearchResult;

      expect(result).toBeDefined();
      expect(Array.isArray(result.results)).toBe(true);
      expect(result.results.length).toBeGreaterThan(0);
    });

    it("should get memory history", async () => {
      // Add and update a memory to create history
      const addResult = (await memory.add(
        "I like swimming in warm water",
        userId,
      )) as SearchResult;

      if (!addResult.results?.[0]?.id) {
        throw new Error("Failed to create test memory");
      }

      const memoryId = addResult.results[0].id;
      await memory.update(memoryId, "Updated content");

      const history = await memory.history(memoryId);

      expect(history).toBeDefined();
      expect(Array.isArray(history)).toBe(true);
      expect(history.length).toBeGreaterThan(0);
    });

    it("should delete a memory", async () => {
      // First add a memory
      const addResult = (await memory.add(
        "I love to drink vodka in summers",
        userId,
      )) as SearchResult;

      if (!addResult.results?.[0]?.id) {
        throw new Error("Failed to create test memory");
      }

      const memoryId = addResult.results[0].id;

      // Delete the memory
      await memory.delete(memoryId);

      // Try to get the deleted memory - should throw or return null
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
          config: {
            apiKey: process.env.OPENAI_API_KEY || "",
            model: "text-embedding-3-small",
          },
        },
        vectorStore: {
          provider: "memory",
          config: {
            collectionName: "test-memories",
            dimension: 1536,
          },
        },
        llm: {
          provider: "openai",
          config: {
            apiKey: process.env.OPENAI_API_KEY || "",
            model: "gpt-4-turbo-preview",
          },
        },
        historyDbPath: ":memory:", // Use in-memory SQLite for tests
      });
    });

    afterEach(async () => {
      await customMemory.reset();
    });

    it("should work with custom configuration", async () => {
      const result = (await customMemory.add(
        "I love programming in Python",
        userId,
      )) as SearchResult;

      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
      expect(Array.isArray(result.results)).toBe(true);
      expect(result.results.length).toBeGreaterThan(0);
    });

    it("should perform semantic search with custom embeddings", async () => {
      // Add test memories
      await customMemory.add("The weather in London is rainy today", userId);
      await customMemory.add("The temperature in Paris is 25 degrees", userId);

      const result = (await customMemory.search(
        "What is the weather like?",
        userId,
      )) as SearchResult;

      expect(result).toBeDefined();
      expect(Array.isArray(result.results)).toBe(true);
      // Results should be ordered by relevance
      expect(result.results.length).toBeGreaterThan(0);
    });
  });
});
