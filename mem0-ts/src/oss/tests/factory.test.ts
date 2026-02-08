/// <reference types="jest" />
import { VectorStoreFactory } from "../src/utils/factory";
import { AzureAISearch } from "../src/vector_stores/azure_ai_search";
import { PGVector } from "../src/vector_stores/pgvector";

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

    it("should create pgvector vector store", () => {
      const config = {
        collectionName: "test-memories",
        user: "test-user",
        password: "test-password",
        host: "localhost",
        port: 5432,
        embeddingModelDims: 1536,
      };

      const vectorStore = VectorStoreFactory.create("pgvector", config);

      expect(vectorStore).toBeInstanceOf(PGVector);
    });

    it("should throw error for unsupported provider", () => {
      const config = {};

      expect(() => {
        VectorStoreFactory.create("unsupported-provider", config);
      }).toThrow("Unsupported vector store provider: unsupported-provider");
    });
  });
});
