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

  describe("mergeConfig - LLM url passthrough for Ollama", () => {
    const baseEmbedder = {
      provider: "openai",
      config: { apiKey: "test-key" },
    };
    const baseVectorStore = {
      provider: "memory",
      config: { collectionName: "test" },
    };

    it("should preserve url in LLM config when provided", () => {
      const config = ConfigManager.mergeConfig({
        embedder: baseEmbedder,
        vectorStore: baseVectorStore,
        llm: {
          provider: "ollama",
          config: { model: "llama3.2:3b", url: "http://10.0.0.100:11434" },
        },
      });

      expect(config.llm.config.url).toBe("http://10.0.0.100:11434");
    });

    it("should prefer baseURL over url when both are provided", () => {
      const config = ConfigManager.mergeConfig({
        embedder: baseEmbedder,
        vectorStore: baseVectorStore,
        llm: {
          provider: "ollama",
          config: {
            model: "llama3.2:3b",
            baseURL: "http://custom:11434",
            url: "http://fallback:11434",
          },
        },
      });

      expect(config.llm.config.baseURL).toBe("http://custom:11434");
      expect(config.llm.config.url).toBe("http://fallback:11434");
    });

    it("should use default baseURL when no url or baseURL provided", () => {
      const config = ConfigManager.mergeConfig({
        embedder: baseEmbedder,
        vectorStore: baseVectorStore,
        llm: {
          provider: "ollama",
          config: { model: "llama3.2:3b" },
        },
      });

      expect(config.llm.config.url).toBeUndefined();
      expect(config.llm.config.baseURL).toBe("https://api.openai.com/v1");
    });

    it("should preserve url in embedder config (existing behavior)", () => {
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "ollama",
          config: {
            model: "nomic-embed-text",
            url: "http://10.0.0.100:11434",
          },
        },
        vectorStore: baseVectorStore,
        llm: {
          provider: "ollama",
          config: { model: "llama3.2:3b", url: "http://10.0.0.100:11434" },
        },
      });

      expect(config.embedder.config.url).toBe("http://10.0.0.100:11434");
      expect(config.llm.config.url).toBe("http://10.0.0.100:11434");
    });
  });
});
