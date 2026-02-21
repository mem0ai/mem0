/// <reference types="jest" />
import { VectorStoreFactory } from "../src/utils/factory";
import { AzureAISearch } from "../src/vector_stores/azure_ai_search";
import { S3Vectors } from "../src/vector_stores/s3_vectors";

jest.mock("@aws-sdk/client-s3vectors", () => ({
  S3VectorsClient: jest.fn().mockImplementation(() => ({
    send: jest.fn(),
    destroy: jest.fn(),
  })),
  CreateVectorBucketCommand: jest.fn(),
  GetVectorBucketCommand: jest.fn(),
  CreateIndexCommand: jest.fn(),
  GetIndexCommand: jest.fn(),
  PutVectorsCommand: jest.fn(),
  QueryVectorsCommand: jest.fn(),
  GetVectorsCommand: jest.fn(),
  DeleteVectorsCommand: jest.fn(),
  ListVectorsCommand: jest.fn(),
  DeleteIndexCommand: jest.fn(),
  ListIndexesCommand: jest.fn(),
}));

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

    it("should create S3 Vectors vector store", () => {
      const config = {
        vectorBucketName: "test-bucket",
        collectionName: "test-index",
        embeddingModelDims: 1536,
        distanceMetric: "cosine" as const,
      };

      const vectorStore = VectorStoreFactory.create("s3_vectors", config);

      expect(vectorStore).toBeInstanceOf(S3Vectors);
    });

    it("should create S3 Vectors with alternative provider name", () => {
      const config = {
        vectorBucketName: "test-bucket",
        collectionName: "test-index",
        embeddingModelDims: 1536,
      };

      const vectorStore = VectorStoreFactory.create("s3vectors", config);

      expect(vectorStore).toBeInstanceOf(S3Vectors);
    });
  });
});
