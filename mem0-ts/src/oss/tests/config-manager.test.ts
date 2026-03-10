/// <reference types="jest" />
import { ConfigManager } from "../src/config/manager";

describe("ConfigManager", () => {
  describe("mergeConfig - dimension handling", () => {
    const baseLlm = {
      provider: "openai",
      config: { apiKey: "test-key" },
    };

    it("should leave dimension undefined when no explicit dimension or embeddingDims provided", () => {
      const config = ConfigManager.mergeConfig({
        embedder: { provider: "openai", config: { apiKey: "test-key" } },
        vectorStore: { provider: "memory", config: { collectionName: "test" } },
        llm: baseLlm,
      });

      // Dimension should be undefined so Memory._autoInitialize() will
      // auto-detect it via a probe embedding at runtime.
      expect(config.vectorStore.config.dimension).toBeUndefined();
    });

    it("should use embeddingDims from embedder config when provided", () => {
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "ollama",
          config: { model: "nomic-embed-text", embeddingDims: 768 },
        },
        vectorStore: { provider: "qdrant", config: { collectionName: "test" } },
        llm: baseLlm,
      });

      expect(config.vectorStore.config.dimension).toBe(768);
    });

    it("should prefer explicit vector store dimension over embedder dims", () => {
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "ollama",
          config: { model: "nomic-embed-text", embeddingDims: 768 },
        },
        vectorStore: {
          provider: "qdrant",
          config: { collectionName: "test", dimension: 1024 },
        },
        llm: baseLlm,
      });

      expect(config.vectorStore.config.dimension).toBe(1024);
    });

    it("should leave dimension undefined when using a custom client without explicit dims", () => {
      const mockClient = { someMethod: () => {} };
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "ollama",
          config: { model: "nomic-embed-text" },
        },
        vectorStore: {
          provider: "qdrant",
          config: { collectionName: "test", client: mockClient },
        },
        llm: baseLlm,
      });

      // No embeddingDims and no explicit dimension → should be undefined
      // for auto-detection at runtime.
      expect(config.vectorStore.config.dimension).toBeUndefined();
    });

    it("should use embeddingDims when using a custom client", () => {
      const mockClient = { someMethod: () => {} };
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "ollama",
          config: { model: "nomic-embed-text", embeddingDims: 768 },
        },
        vectorStore: {
          provider: "qdrant",
          config: { collectionName: "test", client: mockClient },
        },
        llm: baseLlm,
      });

      expect(config.vectorStore.config.dimension).toBe(768);
    });
  });
});
