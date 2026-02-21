/// <reference types="jest" />

const mockUpsert = jest.fn();
const mockQuery = jest.fn();
const mockFetch = jest.fn();
const mockDeleteOne = jest.fn();
const mockDescribeIndexStats = jest.fn();

const mockNamespace = jest.fn().mockImplementation(() => ({
  upsert: mockUpsert,
  query: mockQuery,
  fetch: mockFetch,
  deleteOne: mockDeleteOne,
  describeIndexStats: mockDescribeIndexStats,
}));

const mockIndex = jest.fn().mockImplementation(() => ({
  upsert: mockUpsert,
  query: mockQuery,
  fetch: mockFetch,
  deleteOne: mockDeleteOne,
  describeIndexStats: mockDescribeIndexStats,
  namespace: mockNamespace,
}));

const mockListIndexes = jest.fn();
const mockCreateIndex = jest.fn();
const mockDeleteIndex = jest.fn();
const mockDescribeIndex = jest.fn();

jest.mock(
  "@pinecone-database/pinecone",
  () => ({
    Pinecone: jest.fn().mockImplementation(() => ({
      index: mockIndex,
      listIndexes: mockListIndexes,
      createIndex: mockCreateIndex,
      deleteIndex: mockDeleteIndex,
      describeIndex: mockDescribeIndex,
    })),
  }),
  { virtual: true },
);

import { Pinecone } from "../src/vector_stores/pinecone";

describe("Pinecone", () => {
  const defaultConfig = {
    apiKey: "test-api-key",
    collectionName: "test-index",
    embeddingModelDims: 1536,
    metric: "cosine" as const,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    // Default mock implementations
    mockListIndexes.mockResolvedValue({ indexes: [] });
    mockCreateIndex.mockResolvedValue({});
    mockDescribeIndex.mockResolvedValue({ status: { ready: true } });
  });

  describe("constructor", () => {
    it("should throw error if embeddingModelDims is missing", () => {
      expect(() => {
        new Pinecone({
          apiKey: "test-key",
        } as any);
      }).toThrow("embeddingModelDims is required");
    });

    it("should throw error if apiKey is missing and not in env", () => {
      const originalEnv = process.env.PINECONE_API_KEY;
      delete process.env.PINECONE_API_KEY;

      expect(() => {
        new Pinecone({
          embeddingModelDims: 1536,
        } as any);
      }).toThrow("Pinecone API key must be provided");

      process.env.PINECONE_API_KEY = originalEnv;
    });

    it("should create instance with valid config", () => {
      const store = new Pinecone(defaultConfig);
      expect(store).toBeInstanceOf(Pinecone);
    });

    it("should use apiKey from environment variable", () => {
      const originalEnv = process.env.PINECONE_API_KEY;
      process.env.PINECONE_API_KEY = "env-api-key";

      const store = new Pinecone({
        embeddingModelDims: 1536,
      });
      expect(store).toBeInstanceOf(Pinecone);

      process.env.PINECONE_API_KEY = originalEnv;
    });

    it("should use default values for optional config", () => {
      const store = new Pinecone({
        apiKey: "test-key",
        embeddingModelDims: 1536,
      });
      expect(store).toBeInstanceOf(Pinecone);
    });
  });

  describe("initialize", () => {
    it("should create index if not exists with serverless config", async () => {
      mockListIndexes.mockResolvedValue({ indexes: [] });

      const store = new Pinecone({
        ...defaultConfig,
        serverlessConfig: {
          cloud: "aws",
          region: "us-east-1",
        },
      });
      await store.initialize();

      expect(mockCreateIndex).toHaveBeenCalledWith({
        name: "test-index",
        dimension: 1536,
        metric: "cosine",
        spec: {
          serverless: {
            cloud: "aws",
            region: "us-east-1",
          },
        },
      });
    });

    it("should create index with pod config", async () => {
      mockListIndexes.mockResolvedValue({ indexes: [] });

      const store = new Pinecone({
        ...defaultConfig,
        podConfig: {
          environment: "us-west1-gcp",
          podType: "p1.x1",
          pods: 2,
        },
      });
      await store.initialize();

      expect(mockCreateIndex).toHaveBeenCalledWith({
        name: "test-index",
        dimension: 1536,
        metric: "cosine",
        spec: {
          pod: {
            environment: "us-west1-gcp",
            podType: "p1.x1",
            pods: 2,
            replicas: 1,
            shards: 1,
          },
        },
      });
    });

    it("should use default serverless config if none provided", async () => {
      mockListIndexes.mockResolvedValue({ indexes: [] });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      expect(mockCreateIndex).toHaveBeenCalledWith({
        name: "test-index",
        dimension: 1536,
        metric: "cosine",
        spec: {
          serverless: {
            cloud: "aws",
            region: "us-east-1",
          },
        },
      });
    });

    it("should not create index if it already exists", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      expect(mockCreateIndex).not.toHaveBeenCalled();
    });

    it("should wait for index to be ready", async () => {
      mockListIndexes.mockResolvedValue({ indexes: [] });
      mockDescribeIndex
        .mockResolvedValueOnce({ status: { ready: false } })
        .mockResolvedValueOnce({ status: { ready: false } })
        .mockResolvedValueOnce({ status: { ready: true } });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      expect(mockDescribeIndex).toHaveBeenCalledTimes(3);
    });
  });

  describe("insert", () => {
    it("should insert vectors with correct format", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockUpsert.mockResolvedValue({});

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      const vectors = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
      ];
      const ids = ["vec-1", "vec-2"];
      const payloads = [{ key: "value1" }, { key: "value2" }];

      await store.insert(vectors, ids, payloads);

      expect(mockUpsert).toHaveBeenCalledWith([
        { id: "vec-1", values: [0.1, 0.2, 0.3], metadata: { key: "value1" } },
        { id: "vec-2", values: [0.4, 0.5, 0.6], metadata: { key: "value2" } },
      ]);
    });

    it("should batch upsert when exceeding batch size", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockUpsert.mockResolvedValue({});

      const store = new Pinecone({
        ...defaultConfig,
        batchSize: 2,
      });
      await store.initialize();

      const vectors = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
        [0.7, 0.8, 0.9],
      ];
      const ids = ["vec-1", "vec-2", "vec-3"];
      const payloads = [{}, {}, {}];

      await store.insert(vectors, ids, payloads);

      expect(mockUpsert).toHaveBeenCalledTimes(2);
    });

    it("should use namespace when configured", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockUpsert.mockResolvedValue({});

      const store = new Pinecone({
        ...defaultConfig,
        namespace: "test-namespace",
      });
      await store.initialize();

      await store.insert([[0.1, 0.2, 0.3]], ["vec-1"], [{}]);

      expect(mockNamespace).toHaveBeenCalledWith("test-namespace");
    });
  });

  describe("search", () => {
    it("should query vectors and return results", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockQuery.mockResolvedValue({
        matches: [
          { id: "vec-1", score: 0.95, metadata: { userId: "user1" } },
          { id: "vec-2", score: 0.85, metadata: { userId: "user2" } },
        ],
      });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      const results = await store.search([0.1, 0.2, 0.3], 5);

      expect(results).toHaveLength(2);
      expect(results[0].id).toBe("vec-1");
      expect(results[0].score).toBe(0.95);
      expect(results[0].payload).toEqual({ userId: "user1" });
      expect(results[1].id).toBe("vec-2");
      expect(results[1].score).toBe(0.85);
    });

    it("should apply equality filters correctly", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockQuery.mockResolvedValue({ matches: [] });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      await store.search([0.1, 0.2, 0.3], 5, { userId: "user1" });

      expect(mockQuery).toHaveBeenCalledWith({
        vector: [0.1, 0.2, 0.3],
        topK: 5,
        includeMetadata: true,
        includeValues: false,
        filter: { userId: { $eq: "user1" } },
      });
    });

    it("should apply range filters correctly", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockQuery.mockResolvedValue({ matches: [] });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      await store.search([0.1, 0.2, 0.3], 5, {
        timestamp: { gte: 100, lte: 200 },
      });

      expect(mockQuery).toHaveBeenCalledWith({
        vector: [0.1, 0.2, 0.3],
        topK: 5,
        includeMetadata: true,
        includeValues: false,
        filter: { timestamp: { $gte: 100, $lte: 200 } },
      });
    });

    it("should combine multiple filters", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockQuery.mockResolvedValue({ matches: [] });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      await store.search([0.1, 0.2, 0.3], 5, {
        userId: "user1",
        agentId: "agent1",
      });

      expect(mockQuery).toHaveBeenCalledWith({
        vector: [0.1, 0.2, 0.3],
        topK: 5,
        includeMetadata: true,
        includeValues: false,
        filter: {
          userId: { $eq: "user1" },
          agentId: { $eq: "agent1" },
        },
      });
    });
  });

  describe("get", () => {
    it("should retrieve vector by ID", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockFetch.mockResolvedValue({
        records: {
          "vec-1": { id: "vec-1", metadata: { key: "value" } },
        },
      });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      const result = await store.get("vec-1");

      expect(result).not.toBeNull();
      expect(result?.id).toBe("vec-1");
      expect(result?.payload).toEqual({ key: "value" });
    });

    it("should return null if vector not found", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockFetch.mockResolvedValue({ records: {} });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      const result = await store.get("nonexistent");

      expect(result).toBeNull();
    });

    it("should return null on not found error", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockFetch.mockRejectedValue(new Error("Vector not found"));

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      const result = await store.get("vec-1");

      expect(result).toBeNull();
    });
  });

  describe("update", () => {
    it("should update vector using insert", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockUpsert.mockResolvedValue({});

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      await store.update("vec-1", [0.1, 0.2, 0.3], { updated: true });

      expect(mockUpsert).toHaveBeenCalledWith([
        { id: "vec-1", values: [0.1, 0.2, 0.3], metadata: { updated: true } },
      ]);
    });
  });

  describe("delete", () => {
    it("should delete vector by ID", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockDeleteOne.mockResolvedValue({});

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      await store.delete("vec-1");

      expect(mockDeleteOne).toHaveBeenCalledWith("vec-1");
    });
  });

  describe("deleteCol", () => {
    it("should delete the index", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockDeleteIndex.mockResolvedValue({});

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      await store.deleteCol();

      expect(mockDeleteIndex).toHaveBeenCalledWith("test-index");
    });
  });

  describe("list", () => {
    it("should list vectors using zero vector query", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockQuery.mockResolvedValue({
        matches: [
          { id: "vec-1", metadata: { key: "value1" } },
          { id: "vec-2", metadata: { key: "value2" } },
        ],
      });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      const [results, count] = await store.list(undefined, 100);

      expect(results).toHaveLength(2);
      expect(count).toBe(2);
      expect(results[0].id).toBe("vec-1");
    });

    it("should apply filters when listing", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockQuery.mockResolvedValue({ matches: [] });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      await store.list({ userId: "user1" }, 100);

      expect(mockQuery).toHaveBeenCalledWith(
        expect.objectContaining({
          filter: { userId: { $eq: "user1" } },
        }),
      );
    });
  });

  describe("getUserId / setUserId", () => {
    it("should get and set user ID", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      expect(await store.getUserId()).toBe("");

      await store.setUserId("user-123");
      expect(await store.getUserId()).toBe("user-123");
    });
  });

  describe("getStats", () => {
    it("should return index statistics", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockDescribeIndexStats.mockResolvedValue({
        totalVectorCount: 100,
        namespaces: {},
      });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      const stats = await store.getStats();

      expect(stats.totalVectorCount).toBe(100);
    });
  });

  describe("count", () => {
    it("should return total vector count", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockDescribeIndexStats.mockResolvedValue({
        totalVectorCount: 100,
        namespaces: {},
      });

      const store = new Pinecone(defaultConfig);
      await store.initialize();

      const count = await store.count();

      expect(count).toBe(100);
    });

    it("should return namespace vector count when namespace is set", async () => {
      mockListIndexes.mockResolvedValue({
        indexes: [{ name: "test-index" }],
      });
      mockDescribeIndexStats.mockResolvedValue({
        totalVectorCount: 100,
        namespaces: {
          "test-namespace": { vectorCount: 50 },
        },
      });

      const store = new Pinecone({
        ...defaultConfig,
        namespace: "test-namespace",
      });
      await store.initialize();

      const count = await store.count();

      expect(count).toBe(50);
    });
  });
});
