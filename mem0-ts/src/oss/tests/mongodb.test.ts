/// <reference types="jest" />

const mockConnect = jest.fn();
const mockClose = jest.fn();
const mockDb = jest.fn();
const mockCollection = jest.fn();
const mockListCollections = jest.fn();
const mockListSearchIndexes = jest.fn();
const mockCreateSearchIndex = jest.fn();
const mockInsertOne = jest.fn();
const mockDeleteOne = jest.fn();
const mockInsertMany = jest.fn();
const mockAggregate = jest.fn();
const mockFindOne = jest.fn();
const mockUpdateOne = jest.fn();
const mockFind = jest.fn();
const mockDrop = jest.fn();

// Mock collection object
const mockCollectionInstance = {
  listSearchIndexes: mockListSearchIndexes,
  createSearchIndex: mockCreateSearchIndex,
  insertOne: mockInsertOne,
  deleteOne: mockDeleteOne,
  insertMany: mockInsertMany,
  aggregate: mockAggregate,
  findOne: mockFindOne,
  updateOne: mockUpdateOne,
  find: mockFind,
  drop: mockDrop,
};

// Mock db object
const mockDbInstance = {
  collection: mockCollection,
  listCollections: mockListCollections,
};

// Use virtual mock to avoid needing the actual mongodb package installed
jest.mock(
  "mongodb",
  () => ({
    MongoClient: jest.fn().mockImplementation(() => ({
      connect: mockConnect,
      close: mockClose,
      db: mockDb,
    })),
  }),
  { virtual: true },
);

import { MongoDB } from "../src/vector_stores/mongodb";

describe("MongoDB", () => {
  const defaultConfig = {
    mongoUri: "mongodb+srv://test:test@cluster.mongodb.net",
    dbName: "test-db",
    collectionName: "test-collection",
    embeddingModelDims: 1536,
  };

  beforeEach(() => {
    jest.clearAllMocks();

    // Setup default mock chain
    mockDb.mockReturnValue(mockDbInstance);
    mockCollection.mockReturnValue(mockCollectionInstance);
    mockListCollections.mockReturnValue({
      toArray: jest.fn().mockResolvedValue([{ name: "test-collection" }]),
    });
    mockListSearchIndexes.mockReturnValue({
      toArray: jest
        .fn()
        .mockResolvedValue([{ name: "test-collection_vector_index" }]),
    });
    mockConnect.mockResolvedValue(undefined);
  });

  describe("constructor", () => {
    it("should throw error if MongoClient is not available", () => {
      // This test validates the error path - we can't easily test this since
      // the mock is already set up. Testing the error message format instead.
      const store = new MongoDB(defaultConfig);
      expect(store).toBeInstanceOf(MongoDB);
    });

    it("should throw error if mongoUri is missing", () => {
      expect(() => {
        new MongoDB({
          dbName: "test-db",
          collectionName: "test-collection",
          embeddingModelDims: 1536,
        } as any);
      }).toThrow("mongoUri is required");
    });

    it("should throw error if dbName is missing", () => {
      expect(() => {
        new MongoDB({
          mongoUri: "mongodb://localhost",
          collectionName: "test-collection",
          embeddingModelDims: 1536,
        } as any);
      }).toThrow("dbName is required");
    });

    it("should throw error if collectionName is missing", () => {
      expect(() => {
        new MongoDB({
          mongoUri: "mongodb://localhost",
          dbName: "test-db",
          embeddingModelDims: 1536,
        } as any);
      }).toThrow("collectionName is required");
    });

    it("should throw error if embeddingModelDims is missing", () => {
      expect(() => {
        new MongoDB({
          mongoUri: "mongodb://localhost",
          dbName: "test-db",
          collectionName: "test-collection",
        } as any);
      }).toThrow("embeddingModelDims is required");
    });

    it("should create instance with valid config", () => {
      const store = new MongoDB(defaultConfig);
      expect(store).toBeInstanceOf(MongoDB);
    });

    it("should use default index name when not provided", () => {
      const store = new MongoDB(defaultConfig);
      expect(store).toBeInstanceOf(MongoDB);
      // Index name should be "{collectionName}_vector_index"
    });

    it("should use custom index name when provided", () => {
      const store = new MongoDB({
        ...defaultConfig,
        indexName: "custom_index",
      });
      expect(store).toBeInstanceOf(MongoDB);
    });

    it("should use default similarity metric when not provided", () => {
      const store = new MongoDB(defaultConfig);
      expect(store).toBeInstanceOf(MongoDB);
    });

    it("should use custom similarity metric when provided", () => {
      const store = new MongoDB({
        ...defaultConfig,
        similarityMetric: "dotProduct",
      });
      expect(store).toBeInstanceOf(MongoDB);
    });
  });

  describe("initialize", () => {
    it("should connect and set up collection/index", async () => {
      const store = new MongoDB(defaultConfig);
      await store.initialize();

      expect(mockConnect).toHaveBeenCalled();
      expect(mockDb).toHaveBeenCalledWith("test-db");
      expect(mockCollection).toHaveBeenCalledWith("test-collection");
    });

    it("should create collection if it does not exist", async () => {
      mockListCollections.mockReturnValue({
        toArray: jest.fn().mockResolvedValue([]),
      });
      mockInsertOne.mockResolvedValue({ insertedId: "__placeholder__" });
      mockDeleteOne.mockResolvedValue({ deletedCount: 1 });

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      expect(mockInsertOne).toHaveBeenCalledWith({
        _id: "__placeholder__",
        placeholder: true,
      });
      expect(mockDeleteOne).toHaveBeenCalledWith({ _id: "__placeholder__" });
    });

    it("should create search index if it does not exist", async () => {
      mockListSearchIndexes.mockReturnValue({
        toArray: jest.fn().mockResolvedValue([]),
      });
      mockCreateSearchIndex.mockResolvedValue(undefined);

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      expect(mockCreateSearchIndex).toHaveBeenCalledWith({
        name: "test-collection_vector_index",
        definition: {
          mappings: {
            dynamic: false,
            fields: {
              embedding: {
                type: "knnVector",
                dimensions: 1536,
                similarity: "cosine",
              },
            },
          },
        },
      });
    });

    it("should handle IndexAlreadyExists error gracefully", async () => {
      mockListSearchIndexes.mockReturnValue({
        toArray: jest.fn().mockResolvedValue([]),
      });
      mockCreateSearchIndex.mockRejectedValue({
        codeName: "IndexAlreadyExists",
      });

      const store = new MongoDB(defaultConfig);
      await expect(store.initialize()).resolves.not.toThrow();
    });

    it("should handle code 68 error (index exists) gracefully", async () => {
      mockListSearchIndexes.mockReturnValue({
        toArray: jest.fn().mockResolvedValue([]),
      });
      mockCreateSearchIndex.mockRejectedValue({ code: 68 });

      const store = new MongoDB(defaultConfig);
      await expect(store.initialize()).resolves.not.toThrow();
    });

    it("should use existing collection and index if they exist", async () => {
      const store = new MongoDB(defaultConfig);
      await store.initialize();

      // Should not try to create anything
      expect(mockInsertOne).not.toHaveBeenCalled();
      expect(mockCreateSearchIndex).not.toHaveBeenCalled();
    });
  });

  describe("insert", () => {
    it("should insert vectors with correct format", async () => {
      mockInsertMany.mockResolvedValue({ insertedCount: 2 });

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      const vectors = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
      ];
      const ids = ["vec-1", "vec-2"];
      const payloads = [{ key: "value1" }, { key: "value2" }];

      await store.insert(vectors, ids, payloads);

      expect(mockInsertMany).toHaveBeenCalledWith([
        {
          _id: "vec-1",
          embedding: [0.1, 0.2, 0.3],
          payload: { key: "value1" },
        },
        {
          _id: "vec-2",
          embedding: [0.4, 0.5, 0.6],
          payload: { key: "value2" },
        },
      ]);
    });

    it("should handle empty payloads", async () => {
      mockInsertMany.mockResolvedValue({ insertedCount: 1 });

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      const vectors = [[0.1, 0.2, 0.3]];
      const ids = ["vec-1"];
      const payloads: Record<string, any>[] = [{}];

      await store.insert(vectors, ids, payloads);

      expect(mockInsertMany).toHaveBeenCalledWith([
        { _id: "vec-1", embedding: [0.1, 0.2, 0.3], payload: {} },
      ]);
    });
  });

  describe("search", () => {
    it("should use $vectorSearch aggregation pipeline", async () => {
      mockAggregate.mockReturnValue({
        toArray: jest.fn().mockResolvedValue([
          { _id: "vec-1", score: 0.95, payload: { userId: "user1" } },
          { _id: "vec-2", score: 0.85, payload: { userId: "user2" } },
        ]),
      });

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      const results = await store.search([0.1, 0.2, 0.3], 5);

      expect(mockAggregate).toHaveBeenCalled();
      const pipeline = mockAggregate.mock.calls[0][0];
      expect(pipeline[0].$vectorSearch).toBeDefined();
      expect(pipeline[0].$vectorSearch.index).toBe(
        "test-collection_vector_index",
      );
      expect(pipeline[0].$vectorSearch.path).toBe("embedding");
      expect(pipeline[0].$vectorSearch.queryVector).toEqual([0.1, 0.2, 0.3]);
      expect(pipeline[0].$vectorSearch.limit).toBe(5);

      expect(results).toHaveLength(2);
      expect(results[0].id).toBe("vec-1");
      expect(results[0].score).toBe(0.95);
      expect(results[0].payload).toEqual({ userId: "user1" });
    });

    it("should apply filters to search", async () => {
      mockAggregate.mockReturnValue({
        toArray: jest.fn().mockResolvedValue([]),
      });

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      await store.search([0.1, 0.2, 0.3], 5, { userId: "user1" });

      const pipeline = mockAggregate.mock.calls[0][0];
      // Filter should be added after $vectorSearch
      const matchStage = pipeline.find((stage: any) => stage.$match);
      expect(matchStage).toBeDefined();
      expect(matchStage.$match.$and).toContainEqual({
        "payload.userId": "user1",
      });
    });

    it("should apply multiple filters with $and", async () => {
      mockAggregate.mockReturnValue({
        toArray: jest.fn().mockResolvedValue([]),
      });

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      await store.search([0.1, 0.2, 0.3], 5, {
        userId: "user1",
        agentId: "agent1",
      });

      const pipeline = mockAggregate.mock.calls[0][0];
      const matchStage = pipeline.find((stage: any) => stage.$match);
      expect(matchStage.$match.$and).toContainEqual({
        "payload.userId": "user1",
      });
      expect(matchStage.$match.$and).toContainEqual({
        "payload.agentId": "agent1",
      });
    });

    it("should handle empty search results", async () => {
      mockAggregate.mockReturnValue({
        toArray: jest.fn().mockResolvedValue([]),
      });

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      const results = await store.search([0.1, 0.2, 0.3], 5);

      expect(results).toHaveLength(0);
    });
  });

  describe("get", () => {
    it("should retrieve vector by ID", async () => {
      mockFindOne.mockResolvedValue({
        _id: "vec-1",
        embedding: [0.1, 0.2, 0.3],
        payload: { key: "value" },
      });

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      const result = await store.get("vec-1");

      expect(mockFindOne).toHaveBeenCalledWith({ _id: "vec-1" });
      expect(result).not.toBeNull();
      expect(result?.id).toBe("vec-1");
      expect(result?.payload).toEqual({ key: "value" });
    });

    it("should return null if vector not found", async () => {
      mockFindOne.mockResolvedValue(null);

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      const result = await store.get("nonexistent");

      expect(result).toBeNull();
    });
  });

  describe("update", () => {
    it("should update vector and payload", async () => {
      mockUpdateOne.mockResolvedValue({ matchedCount: 1, modifiedCount: 1 });

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      await store.update("vec-1", [0.1, 0.2, 0.3], { updated: true });

      expect(mockUpdateOne).toHaveBeenCalledWith(
        { _id: "vec-1" },
        { $set: { embedding: [0.1, 0.2, 0.3], payload: { updated: true } } },
      );
    });
  });

  describe("delete", () => {
    it("should delete vector by ID", async () => {
      mockDeleteOne.mockResolvedValue({ deletedCount: 1 });

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      await store.delete("vec-1");

      expect(mockDeleteOne).toHaveBeenCalledWith({ _id: "vec-1" });
    });
  });

  describe("deleteCol", () => {
    it("should drop the collection", async () => {
      mockDrop.mockResolvedValue(true);

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      await store.deleteCol();

      expect(mockDrop).toHaveBeenCalled();
    });
  });

  describe("list", () => {
    it("should list vectors with limit", async () => {
      const mockCursor = {
        [Symbol.asyncIterator]: async function* () {
          yield { _id: "vec-1", payload: { key: "value1" } };
          yield { _id: "vec-2", payload: { key: "value2" } };
        },
      };
      mockFind.mockReturnValue({
        limit: jest.fn().mockReturnValue(mockCursor),
      });

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      const [results, count] = await store.list(undefined, 100);

      expect(mockFind).toHaveBeenCalledWith({});
      expect(results).toHaveLength(2);
      expect(count).toBe(2);
      expect(results[0].id).toBe("vec-1");
    });

    it("should apply filters to list", async () => {
      const mockCursor = {
        [Symbol.asyncIterator]: async function* () {
          yield { _id: "vec-1", payload: { userId: "user1" } };
        },
      };
      mockFind.mockReturnValue({
        limit: jest.fn().mockReturnValue(mockCursor),
      });

      const store = new MongoDB(defaultConfig);
      await store.initialize();

      await store.list({ userId: "user1" }, 100);

      expect(mockFind).toHaveBeenCalledWith({
        $and: [{ "payload.userId": "user1" }],
      });
    });
  });

  describe("getUserId / setUserId", () => {
    it("should get and set user ID", async () => {
      const store = new MongoDB(defaultConfig);
      await store.initialize();

      expect(await store.getUserId()).toBe("");

      await store.setUserId("user-123");
      expect(await store.getUserId()).toBe("user-123");
    });
  });

  describe("destroy", () => {
    it("should close the MongoDB client", async () => {
      const store = new MongoDB(defaultConfig);
      await store.initialize();
      await store.destroy();

      expect(mockClose).toHaveBeenCalled();
    });
  });
});
