/// <reference types="jest" />
import {
  EmbedderFactory,
  VectorStoreFactory,
} from "../src/utils/factory";
import { LMStudioEmbedder } from "../src/embeddings/lmstudio";
import { AzureAISearch } from "../src/vector_stores/azure_ai_search";

describe("EmbedderFactory", () => {
  describe("create", () => {
    it("should create LM Studio embedder", () => {
      const config = {
        model: "text-embedding-gte-qwen2-1.5b-instruct",
        embeddingDims: 1536,
        baseURL: "http://localhost:1234/v1",
      };

      const embedder = EmbedderFactory.create("lmstudio", config);

      expect(embedder).toBeInstanceOf(LMStudioEmbedder);
    });

    it("should create LM Studio embedder with lmstudio_base_url", () => {
      const config = {
        model: "custom-model",
        lmstudio_base_url: "http://192.168.1.1:1234/v1",
      };

      const embedder = EmbedderFactory.create("lmstudio", config);

      expect(embedder).toBeInstanceOf(LMStudioEmbedder);
    });

    it("should throw error for unsupported embedder provider", () => {
      const config = {};

      expect(() => {
        EmbedderFactory.create("unsupported-embedder", config);
      }).toThrow("Unsupported embedder provider: unsupported-embedder");
    });
  });
});

describe("VectorStoreFactory", () => {
  describe("create", () => {
    it("should create Azure AI Search vector store", () => {
      const config = {
        collectionName: "test-memories",
        serviceName: "test-service",
        apiKey: "test-api-key",
        embeddingModelDims: 1536,
        compressionType: "none" as const,
        useFloat16: false,
        hybridSearch: false,
        vectorFilterMode: "preFilter" as const,
      };

      const vectorStore = VectorStoreFactory.create("azure-ai-search", config);

      expect(vectorStore).toBeInstanceOf(AzureAISearch);
    });

    it("should create memory vector store", () => {
      const config = {
        collectionName: "test-memories",
        dimension: 1536,
      };

      const vectorStore = VectorStoreFactory.create("memory", config);

      expect(vectorStore).toBeDefined();
      expect(vectorStore.constructor.name).toBe("MemoryVectorStore");
    });

    it("should throw error for unsupported provider", () => {
      const config = {};

      expect(() => {
        VectorStoreFactory.create("unsupported-provider", config);
      }).toThrow("Unsupported vector store provider: unsupported-provider");
    });
  });
});
