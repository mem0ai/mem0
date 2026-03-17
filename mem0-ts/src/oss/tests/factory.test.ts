/// <reference types="jest" />
import {
  EmbedderFactory,
  VectorStoreFactory,
} from "../src/utils/factory";
import { LMStudioEmbedder } from "../src/embeddings/lmstudio";
import { AzureAISearch } from "../src/vector_stores/azure_ai_search";

describe("EmbedderFactory", () => {
  describe("create", () => {
    it("should create LM Studio embedder with baseURL", () => {
      const embedder = EmbedderFactory.create("lmstudio", {
        model: "text-embedding-gte-qwen2-1.5b-instruct",
        baseURL: "http://localhost:1234/v1",
      });

      expect(embedder).toBeInstanceOf(LMStudioEmbedder);
    });

    it("should throw error for unsupported embedder provider", () => {
      expect(() => {
        EmbedderFactory.create("unsupported-embedder", {});
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
