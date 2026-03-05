/// <reference types="jest" />
import { ConfigManager } from "../src/config/manager";

describe("ConfigManager", () => {
  describe("mergeConfig", () => {
    it("should use default dimension (1536) when no embedder dims or vector store dimension provided", () => {
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "openai",
          config: {
            apiKey: "test-key",
          },
        },
        vectorStore: {
          provider: "memory",
          config: {
            collectionName: "test",
          },
        },
        llm: {
          provider: "openai",
          config: {
            apiKey: "test-key",
          },
        },
      });

      expect(config.vectorStore.config.dimension).toBe(1536);
    });

    it("should infer vector store dimension from embedder embeddingDims", () => {
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "ollama",
          config: {
            model: "nomic-embed-text",
            embeddingDims: 768,
          },
        },
        vectorStore: {
          provider: "qdrant",
          config: {
            collectionName: "test",
          },
        },
        llm: {
          provider: "openai",
          config: {
            apiKey: "test-key",
          },
        },
      });

      expect(config.vectorStore.config.dimension).toBe(768);
    });

    it("should prefer explicit vector store dimension over embedder dims", () => {
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "ollama",
          config: {
            model: "nomic-embed-text",
            embeddingDims: 768,
          },
        },
        vectorStore: {
          provider: "qdrant",
          config: {
            collectionName: "test",
            dimension: 1024,
          },
        },
        llm: {
          provider: "openai",
          config: {
            apiKey: "test-key",
          },
        },
      });

      expect(config.vectorStore.config.dimension).toBe(1024);
    });

    it("should infer dimension when using a custom client instance", () => {
      const mockClient = { someMethod: () => {} };
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "ollama",
          config: {
            model: "nomic-embed-text",
            embeddingDims: 768,
          },
        },
        vectorStore: {
          provider: "qdrant",
          config: {
            collectionName: "test",
            client: mockClient,
          },
        },
        llm: {
          provider: "openai",
          config: {
            apiKey: "test-key",
          },
        },
      });

      expect(config.vectorStore.config.dimension).toBe(768);
    });
  });
});
