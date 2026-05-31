/**
 * Unit tests for OSS SDK input validation.
 *
 * Validates fixes for:
 * - Undefined/null message handling in add()
 * - Threshold bounds validation (must be 0-1) in search()
 * - TopK validation (must be non-negative) in search() and getAll()
 * - Whitespace-only entity ID rejection in add(), search(), getAll()
 */
/// <reference types="jest" />
import { Memory } from "../src/memory";

jest.setTimeout(15000);

// Mock Google modules to prevent @google/genai crash in CI
jest.mock("../src/embeddings/google", () => ({
  GoogleEmbedder: jest.fn(),
}));
jest.mock("../src/llms/google", () => ({
  GoogleLLM: jest.fn(),
}));

jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest.fn().mockResolvedValue(
      JSON.stringify({
        memory: [{ id: "0", text: "test memory", attributed_to: "user" }],
      }),
    ),
  })),
}));

const mockEmbedding = new Array(1536).fill(0.1);
jest.mock("../src/embeddings/openai", () => ({
  OpenAIEmbedder: jest.fn().mockImplementation(() => ({
    embed: jest.fn().mockResolvedValue(mockEmbedding),
    embedBatch: jest.fn().mockResolvedValue([mockEmbedding]),
  })),
}));

describe("Memory Input Validation", () => {
  let memory: Memory;
  const testUserId = "test-user-validation";

  beforeAll(async () => {
    memory = new Memory({
      version: "v1.1",
      embedder: {
        provider: "openai",
        config: { apiKey: "test-key", model: "text-embedding-3-small" },
      },
      llm: {
        provider: "openai",
        config: { apiKey: "test-key", model: "gpt-5-mini" },
      },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "validation-test" },
      },
    });
    // Wait for initialization
    await new Promise((resolve) => setTimeout(resolve, 2000));
  });

  afterAll(async () => {
    try {
      await memory.reset();
    } catch (e) {
      // ignore cleanup errors
    }
  });

  describe("add() message validation", () => {
    it("should throw error when messages is undefined", async () => {
      await expect(
        // @ts-ignore - intentionally passing undefined
        memory.add(undefined, { userId: testUserId }),
      ).rejects.toThrow("messages is required");
    });

    it("should throw error when messages is null", async () => {
      await expect(
        // @ts-ignore - intentionally passing null
        memory.add(null, { userId: testUserId }),
      ).rejects.toThrow("messages is required");
    });
  });

  describe("search() threshold validation", () => {
    it("should throw error when threshold > 1.0", async () => {
      await expect(
        memory.search("test query", {
          filters: { user_id: testUserId },
          threshold: 1.5,
        }),
      ).rejects.toThrow("Invalid threshold");
    });

    it("should throw error when threshold = 1.1", async () => {
      await expect(
        memory.search("test query", {
          filters: { user_id: testUserId },
          threshold: 1.1,
        }),
      ).rejects.toThrow("Invalid threshold");
    });

    it("should throw error when threshold is negative", async () => {
      await expect(
        memory.search("test query", {
          filters: { user_id: testUserId },
          threshold: -0.5,
        }),
      ).rejects.toThrow("Invalid threshold");
    });

    it("should throw error when threshold = -0.1", async () => {
      await expect(
        memory.search("test query", {
          filters: { user_id: testUserId },
          threshold: -0.1,
        }),
      ).rejects.toThrow("Invalid threshold");
    });

    it("should accept threshold = 0 (edge case)", async () => {
      const result = await memory.search("test query", {
        filters: { user_id: testUserId },
        threshold: 0,
      });
      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
    });

    it("should accept threshold = 1.0 (edge case)", async () => {
      const result = await memory.search("test query", {
        filters: { user_id: testUserId },
        threshold: 1.0,
      });
      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
    });

    it("should accept threshold = 0.5 (normal valid value)", async () => {
      const result = await memory.search("test query", {
        filters: { user_id: testUserId },
        threshold: 0.5,
      });
      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
    });
  });

  describe("search() topK validation", () => {
    it("should throw error when topK is negative", async () => {
      await expect(
        memory.search("test query", {
          filters: { user_id: testUserId },
          topK: -5,
        }),
      ).rejects.toThrow("Invalid topK");
    });

    it("should throw error when topK = -1", async () => {
      await expect(
        memory.search("test query", {
          filters: { user_id: testUserId },
          topK: -1,
        }),
      ).rejects.toThrow("Invalid topK");
    });

    it("should accept topK = 0 (returns empty)", async () => {
      const result = await memory.search("test query", {
        filters: { user_id: testUserId },
        topK: 0,
      });
      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
    });

    it("should accept topK = 20 (normal value)", async () => {
      const result = await memory.search("test query", {
        filters: { user_id: testUserId },
        topK: 20,
      });
      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
    });
  });

  describe("add() entity ID validation", () => {
    it("should throw error when userId is whitespace-only", async () => {
      await expect(
        memory.add("test message", { userId: "   " }),
      ).rejects.toThrow("Invalid userId");
    });

    it("should throw error when userId is tabs and newlines", async () => {
      await expect(
        memory.add("test message", { userId: "\t\n\t" }),
      ).rejects.toThrow("Invalid userId");
    });

    it("should throw error when agentId is whitespace-only", async () => {
      await expect(
        memory.add("test message", { agentId: "   " }),
      ).rejects.toThrow("Invalid agentId");
    });

    it("should throw error when runId is whitespace-only", async () => {
      await expect(
        memory.add("test message", { runId: "   " }),
      ).rejects.toThrow("Invalid runId");
    });

    it("should throw error when userId contains internal whitespace", async () => {
      await expect(
        memory.add("test message", { userId: "user 123" }),
      ).rejects.toThrow("Invalid userId: cannot contain whitespace");
    });

    it("should throw error when userId contains tab character", async () => {
      await expect(
        memory.add("test message", { userId: "user\t123" }),
      ).rejects.toThrow("Invalid userId: cannot contain whitespace");
    });

    it("should accept userId with leading/trailing whitespace (trimmed)", async () => {
      // Should not throw - leading/trailing whitespace is trimmed
      const result = await memory.add("test message", {
        userId: "  valid-user  ",
      });
      expect(result).toBeDefined();
    });
  });

  describe("search() filter entity ID validation", () => {
    it("should throw error when user_id in filters is whitespace-only", async () => {
      await expect(
        memory.search("test query", {
          filters: { user_id: "   " },
        }),
      ).rejects.toThrow("Invalid user_id");
    });

    it("should throw error when agent_id in filters is whitespace-only", async () => {
      await expect(
        memory.search("test query", {
          filters: { agent_id: "   " },
        }),
      ).rejects.toThrow("Invalid agent_id");
    });

    it("should throw error when user_id contains internal whitespace", async () => {
      await expect(
        memory.search("test query", {
          filters: { user_id: "user 123" },
        }),
      ).rejects.toThrow("Invalid user_id: cannot contain whitespace");
    });

    it("should accept user_id with leading/trailing whitespace (trimmed)", async () => {
      const result = await memory.search("test query", {
        filters: { user_id: "  valid-user  " },
      });
      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
    });
  });

  describe("getAll() validation", () => {
    it("should throw error when user_id is whitespace-only", async () => {
      await expect(
        memory.getAll({ filters: { user_id: "   " } }),
      ).rejects.toThrow("Invalid user_id");
    });

    it("should throw error when topK is negative", async () => {
      await expect(
        memory.getAll({ filters: { user_id: testUserId }, topK: -1 }),
      ).rejects.toThrow("Invalid topK");
    });

    it("should throw error when user_id contains internal whitespace", async () => {
      await expect(
        memory.getAll({ filters: { user_id: "user 123" } }),
      ).rejects.toThrow("Invalid user_id: cannot contain whitespace");
    });

    it("should accept user_id with leading/trailing whitespace (trimmed)", async () => {
      const result = await memory.getAll({
        filters: { user_id: "  valid-user  " },
      });
      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
    });
  });
});
