/// <reference types="jest" />

const mockSend = jest.fn();
const mockDestroy = jest.fn();

jest.mock("@aws-sdk/client-s3vectors", () => ({
  S3VectorsClient: jest.fn().mockImplementation(() => ({
    send: mockSend,
    destroy: mockDestroy,
  })),
  CreateVectorBucketCommand: jest.fn().mockImplementation((input) => ({
    input,
    type: "CreateVectorBucketCommand",
  })),
  GetVectorBucketCommand: jest.fn().mockImplementation((input) => ({
    input,
    type: "GetVectorBucketCommand",
  })),
  CreateIndexCommand: jest.fn().mockImplementation((input) => ({
    input,
    type: "CreateIndexCommand",
  })),
  GetIndexCommand: jest.fn().mockImplementation((input) => ({
    input,
    type: "GetIndexCommand",
  })),
  PutVectorsCommand: jest.fn().mockImplementation((input) => ({
    input,
    type: "PutVectorsCommand",
  })),
  QueryVectorsCommand: jest.fn().mockImplementation((input) => ({
    input,
    type: "QueryVectorsCommand",
  })),
  GetVectorsCommand: jest.fn().mockImplementation((input) => ({
    input,
    type: "GetVectorsCommand",
  })),
  DeleteVectorsCommand: jest.fn().mockImplementation((input) => ({
    input,
    type: "DeleteVectorsCommand",
  })),
  ListVectorsCommand: jest.fn().mockImplementation((input) => ({
    input,
    type: "ListVectorsCommand",
  })),
  DeleteIndexCommand: jest.fn().mockImplementation((input) => ({
    input,
    type: "DeleteIndexCommand",
  })),
  ListIndexesCommand: jest.fn().mockImplementation((input) => ({
    input,
    type: "ListIndexesCommand",
  })),
}));

import { S3Vectors } from "../src/vector_stores/s3_vectors";

describe("S3Vectors", () => {
  const defaultConfig = {
    vectorBucketName: "test-bucket",
    collectionName: "test-index",
    embeddingModelDims: 1536,
    distanceMetric: "cosine" as const,
    region: "us-east-1",
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("constructor", () => {
    it("should throw error if vectorBucketName is missing", () => {
      expect(() => {
        new S3Vectors({
          embeddingModelDims: 1536,
        } as any);
      }).toThrow("vectorBucketName is required");
    });

    it("should throw error if embeddingModelDims is missing", () => {
      expect(() => {
        new S3Vectors({
          vectorBucketName: "test-bucket",
        } as any);
      }).toThrow("embeddingModelDims is required");
    });

    it("should create instance with valid config", () => {
      const store = new S3Vectors(defaultConfig);
      expect(store).toBeInstanceOf(S3Vectors);
    });

    it("should use default values for optional config", () => {
      const store = new S3Vectors({
        vectorBucketName: "test-bucket",
        embeddingModelDims: 1536,
      });
      expect(store).toBeInstanceOf(S3Vectors);
    });
  });

  describe("initialize", () => {
    it("should create bucket if not exists", async () => {
      const notFoundError = { name: "NotFoundException" };
      mockSend
        .mockRejectedValueOnce(notFoundError)
        .mockResolvedValueOnce({})
        .mockResolvedValueOnce({});

      const store = new S3Vectors(defaultConfig);
      await store.initialize();

      expect(mockSend).toHaveBeenCalledTimes(3);
      expect(mockSend.mock.calls[0][0].type).toBe("GetVectorBucketCommand");
      expect(mockSend.mock.calls[1][0].type).toBe("CreateVectorBucketCommand");
      expect(mockSend.mock.calls[2][0].type).toBe("GetIndexCommand");
    });

    it("should create index if not exists", async () => {
      const notFoundError = { name: "NotFoundException" };
      mockSend
        .mockResolvedValueOnce({})
        .mockRejectedValueOnce(notFoundError)
        .mockResolvedValueOnce({});

      const store = new S3Vectors(defaultConfig);
      await store.initialize();

      expect(mockSend).toHaveBeenCalledTimes(3);
      expect(mockSend.mock.calls[2][0].type).toBe("CreateIndexCommand");
    });

    it("should use existing bucket and index if they exist", async () => {
      mockSend.mockResolvedValue({});

      const store = new S3Vectors(defaultConfig);
      await store.initialize();

      expect(mockSend).toHaveBeenCalledTimes(2);
      expect(mockSend.mock.calls[0][0].type).toBe("GetVectorBucketCommand");
      expect(mockSend.mock.calls[1][0].type).toBe("GetIndexCommand");
    });
  });

  describe("insert", () => {
    it("should insert vectors with correct format", async () => {
      mockSend.mockResolvedValueOnce({});

      const store = new S3Vectors(defaultConfig);
      const vectors = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
      ];
      const ids = ["vec-1", "vec-2"];
      const payloads = [{ key: "value1" }, { key: "value2" }];

      await store.insert(vectors, ids, payloads);

      expect(mockSend).toHaveBeenCalledTimes(1);
      const command = mockSend.mock.calls[0][0];
      expect(command.type).toBe("PutVectorsCommand");
      expect(command.input.vectorBucketName).toBe("test-bucket");
      expect(command.input.indexName).toBe("test-index");
      expect(command.input.vectors).toHaveLength(2);
      expect(command.input.vectors[0]).toEqual({
        key: "vec-1",
        data: { float32: [0.1, 0.2, 0.3] },
        metadata: { key: "value1" },
      });
    });
  });

  describe("search", () => {
    it("should query vectors and transform results", async () => {
      mockSend.mockResolvedValueOnce({
        vectors: [
          { key: "vec-1", distance: 0.5, metadata: { userId: "user1" } },
          { key: "vec-2", distance: 1.0, metadata: { userId: "user2" } },
        ],
      });

      const store = new S3Vectors(defaultConfig);
      const results = await store.search([0.1, 0.2, 0.3], 5);

      expect(results).toHaveLength(2);
      expect(results[0].id).toBe("vec-1");
      expect(results[0].score).toBeCloseTo(0.666667, 5);
      expect(results[0].payload).toEqual({ userId: "user1" });
      expect(results[1].id).toBe("vec-2");
      expect(results[1].score).toBeCloseTo(0.5, 5);
    });

    it("should apply filters correctly", async () => {
      mockSend.mockResolvedValueOnce({ vectors: [] });

      const store = new S3Vectors(defaultConfig);
      await store.search([0.1, 0.2, 0.3], 5, { userId: "user1" });

      const command = mockSend.mock.calls[0][0];
      expect(command.input.filter).toEqual({ userId: { $eq: "user1" } });
    });

    it("should combine multiple filters with $and", async () => {
      mockSend.mockResolvedValueOnce({ vectors: [] });

      const store = new S3Vectors(defaultConfig);
      await store.search([0.1, 0.2, 0.3], 5, {
        userId: "user1",
        agentId: "agent1",
      });

      const command = mockSend.mock.calls[0][0];
      expect(command.input.filter).toEqual({
        $and: [{ userId: { $eq: "user1" } }, { agentId: { $eq: "agent1" } }],
      });
    });
  });

  describe("get", () => {
    it("should retrieve vector by ID", async () => {
      mockSend.mockResolvedValueOnce({
        vectors: [{ key: "vec-1", metadata: { key: "value" } }],
      });

      const store = new S3Vectors(defaultConfig);
      const result = await store.get("vec-1");

      expect(result).not.toBeNull();
      expect(result?.id).toBe("vec-1");
      expect(result?.payload).toEqual({ key: "value" });
    });

    it("should return null if vector not found", async () => {
      mockSend.mockResolvedValueOnce({ vectors: [] });

      const store = new S3Vectors(defaultConfig);
      const result = await store.get("nonexistent");

      expect(result).toBeNull();
    });

    it("should return null on NotFoundException", async () => {
      mockSend.mockRejectedValueOnce({ name: "NotFoundException" });

      const store = new S3Vectors(defaultConfig);
      const result = await store.get("vec-1");

      expect(result).toBeNull();
    });
  });

  describe("update", () => {
    it("should update vector using insert", async () => {
      mockSend.mockResolvedValueOnce({});

      const store = new S3Vectors(defaultConfig);
      await store.update("vec-1", [0.1, 0.2, 0.3], { updated: true });

      const command = mockSend.mock.calls[0][0];
      expect(command.type).toBe("PutVectorsCommand");
      expect(command.input.vectors[0].key).toBe("vec-1");
    });
  });

  describe("delete", () => {
    it("should delete vector by ID", async () => {
      mockSend.mockResolvedValueOnce({});

      const store = new S3Vectors(defaultConfig);
      await store.delete("vec-1");

      const command = mockSend.mock.calls[0][0];
      expect(command.type).toBe("DeleteVectorsCommand");
      expect(command.input.keys).toEqual(["vec-1"]);
    });
  });

  describe("deleteCol", () => {
    it("should delete the index", async () => {
      mockSend.mockResolvedValueOnce({});

      const store = new S3Vectors(defaultConfig);
      await store.deleteCol();

      const command = mockSend.mock.calls[0][0];
      expect(command.type).toBe("DeleteIndexCommand");
      expect(command.input.indexName).toBe("test-index");
    });
  });

  describe("list", () => {
    it("should list vectors with pagination", async () => {
      mockSend.mockResolvedValueOnce({
        vectors: [
          { key: "vec-1", metadata: { key: "value1" } },
          { key: "vec-2", metadata: { key: "value2" } },
        ],
      });

      const store = new S3Vectors(defaultConfig);
      const [results, count] = await store.list(undefined, 100);

      expect(results).toHaveLength(2);
      expect(count).toBe(2);
      expect(results[0].id).toBe("vec-1");
    });

    it("should warn when filters are provided", async () => {
      const consoleSpy = jest.spyOn(console, "warn").mockImplementation();
      mockSend.mockResolvedValueOnce({ vectors: [] });

      const store = new S3Vectors(defaultConfig);
      await store.list({ userId: "user1" }, 100);

      expect(consoleSpy).toHaveBeenCalledWith(
        "S3 Vectors `list` does not support metadata filtering. Ignoring filters.",
      );
      consoleSpy.mockRestore();
    });
  });

  describe("getUserId / setUserId", () => {
    it("should get and set user ID", async () => {
      const store = new S3Vectors(defaultConfig);

      expect(await store.getUserId()).toBe("");

      await store.setUserId("user-123");
      expect(await store.getUserId()).toBe("user-123");
    });
  });

  describe("destroy", () => {
    it("should call client destroy", async () => {
      const store = new S3Vectors(defaultConfig);
      await store.destroy();

      expect(mockDestroy).toHaveBeenCalled();
    });
  });
});
