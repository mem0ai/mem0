/// <reference types="jest" />

const mockGetOrCreateCollection = jest.fn();
const mockDeleteCollection = jest.fn();
const mockCollectionAdd = jest.fn();
const mockCollectionQuery = jest.fn();
const mockCollectionGet = jest.fn();
const mockCollectionUpdate = jest.fn();
const mockCollectionDelete = jest.fn();

const mockCollection = {
  add: mockCollectionAdd,
  query: mockCollectionQuery,
  get: mockCollectionGet,
  update: mockCollectionUpdate,
  delete: mockCollectionDelete,
};

jest.mock(
  "chromadb",
  () => ({
    ChromaClient: jest.fn().mockImplementation(() => ({
      getOrCreateCollection:
        mockGetOrCreateCollection.mockResolvedValue(mockCollection),
      deleteCollection: mockDeleteCollection,
    })),
    CloudClient: jest.fn().mockImplementation(() => ({
      getOrCreateCollection:
        mockGetOrCreateCollection.mockResolvedValue(mockCollection),
      deleteCollection: mockDeleteCollection,
    })),
  }),
  { virtual: true },
);

import { Chroma } from "../src/vector_stores/chroma";

describe("Chroma", () => {
  const defaultConfig = {
    collectionName: "test-collection",
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("constructor", () => {
    it("should create instance with default collection name", () => {
      const store = new Chroma({});
      expect(store).toBeInstanceOf(Chroma);
    });

    it("should create instance with custom collection name", () => {
      const store = new Chroma({ collectionName: "my-collection" });
      expect(store).toBeInstanceOf(Chroma);
    });

    it("should create instance with host and port", () => {
      const store = new Chroma({
        collectionName: "test",
        host: "localhost",
        port: 8000,
      });
      expect(store).toBeInstanceOf(Chroma);
    });

    it("should create instance with path for local storage", () => {
      const store = new Chroma({
        collectionName: "test",
        path: "./chroma-data",
      });
      expect(store).toBeInstanceOf(Chroma);
    });

    it("should create cloud client with apiKey and tenant", () => {
      const store = new Chroma({
        collectionName: "test",
        apiKey: "test-api-key",
        tenant: "test-tenant",
      });
      expect(store).toBeInstanceOf(Chroma);
    });

    it("should use custom database name for cloud client", () => {
      const store = new Chroma({
        collectionName: "test",
        apiKey: "test-api-key",
        tenant: "test-tenant",
        database: "custom-db",
      });
      expect(store).toBeInstanceOf(Chroma);
    });

    it("should accept existing client", () => {
      const mockClient = {
        getOrCreateCollection: jest.fn(),
        deleteCollection: jest.fn(),
      };
      const store = new Chroma({
        collectionName: "test",
        client: mockClient,
      });
      expect(store).toBeInstanceOf(Chroma);
    });
  });

  describe("initialize", () => {
    it("should create or get collection", async () => {
      const store = new Chroma(defaultConfig);
      await store.initialize();

      expect(mockGetOrCreateCollection).toHaveBeenCalledWith({
        name: "test-collection",
      });
    });

    it("should use default collection name if not provided", async () => {
      const store = new Chroma({});
      await store.initialize();

      expect(mockGetOrCreateCollection).toHaveBeenCalledWith({
        name: "mem0",
      });
    });
  });

  describe("insert", () => {
    it("should insert vectors with correct format", async () => {
      mockCollectionAdd.mockResolvedValueOnce({});

      const store = new Chroma(defaultConfig);
      await store.initialize();

      const vectors = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
      ];
      const ids = ["vec-1", "vec-2"];
      const payloads = [{ key: "value1" }, { key: "value2" }];

      await store.insert(vectors, ids, payloads);

      expect(mockCollectionAdd).toHaveBeenCalledWith({
        ids,
        embeddings: vectors,
        metadatas: payloads,
      });
    });

    it("should sanitize complex metadata values", async () => {
      mockCollectionAdd.mockResolvedValueOnce({});

      const store = new Chroma(defaultConfig);
      await store.initialize();

      const vectors = [[0.1, 0.2, 0.3]];
      const ids = ["vec-1"];
      const payloads = [
        {
          string: "text",
          number: 42,
          boolean: true,
          array: [1, 2, 3],
          object: { nested: "value" },
          nullValue: null,
          undefinedValue: undefined,
        },
      ];

      await store.insert(vectors, ids, payloads);

      expect(mockCollectionAdd).toHaveBeenCalledWith({
        ids,
        embeddings: vectors,
        metadatas: [
          {
            string: "text",
            number: 42,
            boolean: true,
            array: "[1,2,3]",
            object: '{"nested":"value"}',
          },
        ],
      });
    });

    it("should auto-initialize collection if not initialized", async () => {
      mockCollectionAdd.mockResolvedValueOnce({});

      const store = new Chroma(defaultConfig);
      // Don't call initialize explicitly

      await store.insert([[0.1]], ["id1"], [{ key: "value" }]);

      expect(mockGetOrCreateCollection).toHaveBeenCalled();
      expect(mockCollectionAdd).toHaveBeenCalled();
    });
  });

  describe("search", () => {
    it("should query vectors and transform results", async () => {
      mockCollectionQuery.mockResolvedValueOnce({
        ids: [["vec-1", "vec-2"]],
        distances: [[0.5, 1.0]],
        metadatas: [[{ userId: "user1" }, { userId: "user2" }]],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      const results = await store.search([0.1, 0.2, 0.3], 5);

      expect(mockCollectionQuery).toHaveBeenCalledWith({
        queryEmbeddings: [[0.1, 0.2, 0.3]],
        nResults: 5,
      });

      expect(results).toHaveLength(2);
      expect(results[0].id).toBe("vec-1");
      expect(results[0].score).toBeCloseTo(0.666667, 5);
      expect(results[0].payload).toEqual({ userId: "user1" });
      expect(results[1].id).toBe("vec-2");
      expect(results[1].score).toBeCloseTo(0.5, 5);
    });

    it("should apply simple equality filter", async () => {
      mockCollectionQuery.mockResolvedValueOnce({
        ids: [[]],
        distances: [[]],
        metadatas: [[]],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      await store.search([0.1, 0.2, 0.3], 5, { userId: "user1" });

      expect(mockCollectionQuery).toHaveBeenCalledWith({
        queryEmbeddings: [[0.1, 0.2, 0.3]],
        nResults: 5,
        where: { userId: { $eq: "user1" } },
      });
    });

    it("should combine multiple filters with $and", async () => {
      mockCollectionQuery.mockResolvedValueOnce({
        ids: [[]],
        distances: [[]],
        metadatas: [[]],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      await store.search([0.1, 0.2, 0.3], 5, {
        userId: "user1",
        agentId: "agent1",
      });

      expect(mockCollectionQuery).toHaveBeenCalledWith({
        queryEmbeddings: [[0.1, 0.2, 0.3]],
        nResults: 5,
        where: {
          $and: [{ userId: { $eq: "user1" } }, { agentId: { $eq: "agent1" } }],
        },
      });
    });

    it("should handle comparison operators", async () => {
      mockCollectionQuery.mockResolvedValueOnce({
        ids: [[]],
        distances: [[]],
        metadatas: [[]],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      await store.search([0.1, 0.2, 0.3], 5, {
        score: { gte: 0.5, lte: 1.0 },
      });

      expect(mockCollectionQuery).toHaveBeenCalledWith({
        queryEmbeddings: [[0.1, 0.2, 0.3]],
        nResults: 5,
        where: {
          $and: [{ score: { $gte: 0.5 } }, { score: { $lte: 1.0 } }],
        },
      });
    });

    it("should handle $or operator", async () => {
      mockCollectionQuery.mockResolvedValueOnce({
        ids: [[]],
        distances: [[]],
        metadatas: [[]],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      await store.search([0.1, 0.2, 0.3], 5, {
        $or: [{ userId: "user1" }, { userId: "user2" }],
      });

      expect(mockCollectionQuery).toHaveBeenCalledWith({
        queryEmbeddings: [[0.1, 0.2, 0.3]],
        nResults: 5,
        where: {
          $or: [{ userId: { $eq: "user1" } }, { userId: { $eq: "user2" } }],
        },
      });
    });

    it("should skip wildcard filters", async () => {
      mockCollectionQuery.mockResolvedValueOnce({
        ids: [[]],
        distances: [[]],
        metadatas: [[]],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      await store.search([0.1, 0.2, 0.3], 5, { userId: "*" });

      expect(mockCollectionQuery).toHaveBeenCalledWith({
        queryEmbeddings: [[0.1, 0.2, 0.3]],
        nResults: 5,
        where: {},
      });
    });

    it("should handle empty results", async () => {
      mockCollectionQuery.mockResolvedValueOnce({
        ids: [],
        distances: [],
        metadatas: [],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      const results = await store.search([0.1, 0.2, 0.3], 5);

      expect(results).toHaveLength(0);
    });
  });

  describe("get", () => {
    it("should retrieve vector by ID", async () => {
      mockCollectionGet.mockResolvedValueOnce({
        ids: ["vec-1"],
        metadatas: [{ key: "value" }],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      const result = await store.get("vec-1");

      expect(mockCollectionGet).toHaveBeenCalledWith({
        ids: ["vec-1"],
      });

      expect(result).not.toBeNull();
      expect(result?.id).toBe("vec-1");
      expect(result?.payload).toEqual({ key: "value" });
    });

    it("should return null if vector not found", async () => {
      mockCollectionGet.mockResolvedValueOnce({
        ids: [],
        metadatas: [],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      const result = await store.get("nonexistent");

      expect(result).toBeNull();
    });

    it("should return null on error", async () => {
      mockCollectionGet.mockRejectedValueOnce(new Error("Not found"));

      const store = new Chroma(defaultConfig);
      await store.initialize();

      const result = await store.get("vec-1");

      expect(result).toBeNull();
    });
  });

  describe("update", () => {
    it("should update vector and metadata", async () => {
      mockCollectionUpdate.mockResolvedValueOnce({});

      const store = new Chroma(defaultConfig);
      await store.initialize();

      await store.update("vec-1", [0.1, 0.2, 0.3], { updated: true });

      expect(mockCollectionUpdate).toHaveBeenCalledWith({
        ids: ["vec-1"],
        embeddings: [[0.1, 0.2, 0.3]],
        metadatas: [{ updated: true }],
      });
    });

    it("should sanitize metadata on update", async () => {
      mockCollectionUpdate.mockResolvedValueOnce({});

      const store = new Chroma(defaultConfig);
      await store.initialize();

      await store.update("vec-1", [0.1, 0.2, 0.3], {
        nested: { key: "value" },
      });

      expect(mockCollectionUpdate).toHaveBeenCalledWith({
        ids: ["vec-1"],
        embeddings: [[0.1, 0.2, 0.3]],
        metadatas: [{ nested: '{"key":"value"}' }],
      });
    });
  });

  describe("delete", () => {
    it("should delete vector by ID", async () => {
      mockCollectionDelete.mockResolvedValueOnce({});

      const store = new Chroma(defaultConfig);
      await store.initialize();

      await store.delete("vec-1");

      expect(mockCollectionDelete).toHaveBeenCalledWith({
        ids: ["vec-1"],
      });
    });
  });

  describe("deleteCol", () => {
    it("should delete the collection", async () => {
      mockDeleteCollection.mockResolvedValueOnce({});

      const store = new Chroma(defaultConfig);
      await store.initialize();

      await store.deleteCol();

      expect(mockDeleteCollection).toHaveBeenCalledWith({
        name: "test-collection",
      });
    });
  });

  describe("list", () => {
    it("should list vectors without filters", async () => {
      mockCollectionGet.mockResolvedValueOnce({
        ids: ["vec-1", "vec-2"],
        metadatas: [{ key: "value1" }, { key: "value2" }],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      const [results, count] = await store.list(undefined, 100);

      expect(mockCollectionGet).toHaveBeenCalledWith({
        limit: 100,
      });

      expect(results).toHaveLength(2);
      expect(count).toBe(2);
      expect(results[0].id).toBe("vec-1");
      expect(results[0].payload).toEqual({ key: "value1" });
    });

    it("should list vectors with filters", async () => {
      mockCollectionGet.mockResolvedValueOnce({
        ids: ["vec-1"],
        metadatas: [{ userId: "user1" }],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      const [results, count] = await store.list({ userId: "user1" }, 100);

      expect(mockCollectionGet).toHaveBeenCalledWith({
        limit: 100,
        where: { userId: { $eq: "user1" } },
      });

      expect(results).toHaveLength(1);
      expect(count).toBe(1);
    });

    it("should handle empty list", async () => {
      mockCollectionGet.mockResolvedValueOnce({
        ids: [],
        metadatas: [],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      const [results, count] = await store.list(undefined, 100);

      expect(results).toHaveLength(0);
      expect(count).toBe(0);
    });
  });

  describe("getUserId / setUserId", () => {
    it("should get and set user ID", async () => {
      const store = new Chroma(defaultConfig);

      expect(await store.getUserId()).toBe("");

      await store.setUserId("user-123");
      expect(await store.getUserId()).toBe("user-123");
    });
  });

  describe("_generateWhereClause", () => {
    it("should handle all comparison operators", async () => {
      mockCollectionQuery.mockResolvedValue({
        ids: [[]],
        distances: [[]],
        metadatas: [[]],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      // Test $eq
      await store.search([0.1], 1, { field: { $eq: "value" } });
      expect(mockCollectionQuery).toHaveBeenLastCalledWith(
        expect.objectContaining({
          where: { field: { $eq: "value" } },
        }),
      );

      // Test $ne
      await store.search([0.1], 1, { field: { $ne: "value" } });
      expect(mockCollectionQuery).toHaveBeenLastCalledWith(
        expect.objectContaining({
          where: { field: { $ne: "value" } },
        }),
      );

      // Test $gt
      await store.search([0.1], 1, { field: { $gt: 5 } });
      expect(mockCollectionQuery).toHaveBeenLastCalledWith(
        expect.objectContaining({
          where: { field: { $gt: 5 } },
        }),
      );

      // Test $lt
      await store.search([0.1], 1, { field: { $lt: 5 } });
      expect(mockCollectionQuery).toHaveBeenLastCalledWith(
        expect.objectContaining({
          where: { field: { $lt: 5 } },
        }),
      );

      // Test $in
      await store.search([0.1], 1, { field: { $in: [1, 2, 3] } });
      expect(mockCollectionQuery).toHaveBeenLastCalledWith(
        expect.objectContaining({
          where: { field: { $in: [1, 2, 3] } },
        }),
      );

      // Test $nin
      await store.search([0.1], 1, { field: { $nin: [1, 2, 3] } });
      expect(mockCollectionQuery).toHaveBeenLastCalledWith(
        expect.objectContaining({
          where: { field: { $nin: [1, 2, 3] } },
        }),
      );
    });

    it("should handle $and operator", async () => {
      mockCollectionQuery.mockResolvedValue({
        ids: [[]],
        distances: [[]],
        metadatas: [[]],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      await store.search([0.1], 1, {
        $and: [{ userId: "user1" }, { status: "active" }],
      });

      expect(mockCollectionQuery).toHaveBeenLastCalledWith(
        expect.objectContaining({
          where: {
            $and: [{ userId: { $eq: "user1" } }, { status: { $eq: "active" } }],
          },
        }),
      );
    });

    it("should handle null and undefined values in filters", async () => {
      mockCollectionQuery.mockResolvedValue({
        ids: [[]],
        distances: [[]],
        metadatas: [[]],
      });

      const store = new Chroma(defaultConfig);
      await store.initialize();

      await store.search([0.1], 1, {
        field1: "value",
        field2: null,
        field3: undefined,
      });

      expect(mockCollectionQuery).toHaveBeenLastCalledWith(
        expect.objectContaining({
          where: { field1: { $eq: "value" } },
        }),
      );
    });
  });
});
