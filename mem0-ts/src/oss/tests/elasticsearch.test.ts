/// <reference types="jest" />

/**
 * Mock the @elastic/elasticsearch module before any imports.
 * Jest hoists jest.mock calls, but the module must exist for resolution.
 * We use a virtual mock to avoid needing the actual package installed.
 */
const mockSearch = jest.fn();
const mockGet = jest.fn();
const mockUpdate = jest.fn();
const mockDelete = jest.fn();
const mockBulk = jest.fn();
const mockClose = jest.fn();

const mockIndicesExists = jest.fn();
const mockIndicesCreate = jest.fn();
const mockIndicesDelete = jest.fn();

jest.mock(
  "@elastic/elasticsearch",
  () => ({
    Client: jest.fn().mockImplementation(() => ({
      search: mockSearch,
      get: mockGet,
      update: mockUpdate,
      delete: mockDelete,
      bulk: mockBulk,
      close: mockClose,
      indices: {
        exists: mockIndicesExists,
        create: mockIndicesCreate,
        delete: mockIndicesDelete,
      },
    })),
  }),
  { virtual: true },
);

import { Elasticsearch } from "../src/vector_stores/elasticsearch";

describe("Elasticsearch", () => {
  const defaultConfig = {
    host: "http://localhost",
    port: 9200,
    user: "elastic",
    password: "password",
    collectionName: "test-index",
    embeddingModelDims: 1536,
  };

  const cloudConfig = {
    cloudId: "my-deployment:abc123",
    apiKey: "test-api-key",
    collectionName: "test-index",
    embeddingModelDims: 1536,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("constructor", () => {
    it("should throw error if embeddingModelDims is missing", () => {
      expect(() => {
        new Elasticsearch({
          host: "http://localhost",
          user: "elastic",
          password: "password",
        } as any);
      }).toThrow("embeddingModelDims is required");
    });

    it("should throw error if neither cloudId nor host is provided", () => {
      expect(() => {
        new Elasticsearch({
          apiKey: "test-key",
          embeddingModelDims: 1536,
        } as any);
      }).toThrow("Either cloudId or host must be provided");
    });

    it("should throw error if no authentication is provided", () => {
      expect(() => {
        new Elasticsearch({
          host: "http://localhost",
          embeddingModelDims: 1536,
        } as any);
      }).toThrow("Either apiKey or user/password must be provided");
    });

    it("should create instance with basic auth config", () => {
      const store = new Elasticsearch(defaultConfig);
      expect(store).toBeInstanceOf(Elasticsearch);
    });

    it("should create instance with cloud config", () => {
      const store = new Elasticsearch(cloudConfig);
      expect(store).toBeInstanceOf(Elasticsearch);
    });

    it("should create instance with API key and host", () => {
      const store = new Elasticsearch({
        host: "http://localhost:9200",
        apiKey: "test-api-key",
        embeddingModelDims: 1536,
      });
      expect(store).toBeInstanceOf(Elasticsearch);
    });

    it("should use default collection name if not provided", () => {
      const store = new Elasticsearch({
        host: "http://localhost",
        user: "elastic",
        password: "password",
        embeddingModelDims: 1536,
      });
      expect(store).toBeInstanceOf(Elasticsearch);
    });
  });

  describe("initialize", () => {
    it("should create index if not exists", async () => {
      mockIndicesExists.mockResolvedValueOnce(false);
      mockIndicesCreate.mockResolvedValueOnce({});

      const store = new Elasticsearch(defaultConfig);
      await store.initialize();

      expect(mockIndicesExists).toHaveBeenCalledWith({ index: "test-index" });
      expect(mockIndicesCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          index: "test-index",
          mappings: expect.objectContaining({
            properties: expect.objectContaining({
              vector: expect.objectContaining({
                type: "dense_vector",
                dims: 1536,
              }),
            }),
          }),
        }),
      );
    });

    it("should not create index if it already exists", async () => {
      mockIndicesExists.mockResolvedValueOnce(true);

      const store = new Elasticsearch(defaultConfig);
      await store.initialize();

      expect(mockIndicesExists).toHaveBeenCalled();
      expect(mockIndicesCreate).not.toHaveBeenCalled();
    });

    it("should skip index creation if autoCreateIndex is false", async () => {
      const store = new Elasticsearch({
        ...defaultConfig,
        autoCreateIndex: false,
      });
      await store.initialize();

      expect(mockIndicesExists).not.toHaveBeenCalled();
      expect(mockIndicesCreate).not.toHaveBeenCalled();
    });
  });

  describe("insert", () => {
    it("should insert vectors using bulk operation", async () => {
      mockBulk.mockResolvedValueOnce({ errors: false, items: [] });

      const store = new Elasticsearch(defaultConfig);
      const vectors = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
      ];
      const ids = ["vec-1", "vec-2"];
      const payloads = [{ key: "value1" }, { key: "value2" }];

      await store.insert(vectors, ids, payloads);

      expect(mockBulk).toHaveBeenCalledWith({
        operations: [
          { index: { _index: "test-index", _id: "vec-1" } },
          { vector: [0.1, 0.2, 0.3], metadata: { key: "value1" } },
          { index: { _index: "test-index", _id: "vec-2" } },
          { vector: [0.4, 0.5, 0.6], metadata: { key: "value2" } },
        ],
        refresh: true,
      });
    });

    it("should throw error if bulk operation fails", async () => {
      mockBulk.mockResolvedValueOnce({
        errors: true,
        items: [{ index: { error: { reason: "test error" } } }],
      });

      const store = new Elasticsearch(defaultConfig);
      await expect(
        store.insert([[0.1, 0.2, 0.3]], ["vec-1"], [{ key: "value" }]),
      ).rejects.toThrow("Bulk insert failed");
    });

    it("should handle empty payloads", async () => {
      mockBulk.mockResolvedValueOnce({ errors: false, items: [] });

      const store = new Elasticsearch(defaultConfig);
      await store.insert([[0.1, 0.2, 0.3]], ["vec-1"], []);

      expect(mockBulk).toHaveBeenCalledWith(
        expect.objectContaining({
          operations: expect.arrayContaining([
            expect.objectContaining({ metadata: {} }),
          ]),
        }),
      );
    });
  });

  describe("search", () => {
    it("should search using kNN query", async () => {
      mockSearch.mockResolvedValueOnce({
        hits: {
          hits: [
            {
              _id: "vec-1",
              _score: 0.95,
              _source: { metadata: { userId: "user1" } },
            },
            {
              _id: "vec-2",
              _score: 0.85,
              _source: { metadata: { userId: "user2" } },
            },
          ],
        },
      });

      const store = new Elasticsearch(defaultConfig);
      const results = await store.search([0.1, 0.2, 0.3], 5);

      expect(results).toHaveLength(2);
      expect(results[0].id).toBe("vec-1");
      expect(results[0].score).toBe(0.95);
      expect(results[0].payload).toEqual({ userId: "user1" });
      expect(results[1].id).toBe("vec-2");
      expect(results[1].score).toBe(0.85);
    });

    it("should apply filters correctly", async () => {
      mockSearch.mockResolvedValueOnce({ hits: { hits: [] } });

      const store = new Elasticsearch(defaultConfig);
      await store.search([0.1, 0.2, 0.3], 5, { userId: "user1" });

      expect(mockSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          knn: expect.objectContaining({
            filter: {
              bool: {
                must: [{ term: { "metadata.userId": "user1" } }],
              },
            },
          }),
        }),
      );
    });

    it("should combine multiple filters", async () => {
      mockSearch.mockResolvedValueOnce({ hits: { hits: [] } });

      const store = new Elasticsearch(defaultConfig);
      await store.search([0.1, 0.2, 0.3], 5, {
        userId: "user1",
        agentId: "agent1",
      });

      expect(mockSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          knn: expect.objectContaining({
            filter: {
              bool: {
                must: [
                  { term: { "metadata.userId": "user1" } },
                  { term: { "metadata.agentId": "agent1" } },
                ],
              },
            },
          }),
        }),
      );
    });

    it("should ignore undefined filter values", async () => {
      mockSearch.mockResolvedValueOnce({ hits: { hits: [] } });

      const store = new Elasticsearch(defaultConfig);
      await store.search([0.1, 0.2, 0.3], 5, {
        userId: "user1",
        agentId: undefined,
      });

      expect(mockSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          knn: expect.objectContaining({
            filter: {
              bool: {
                must: [{ term: { "metadata.userId": "user1" } }],
              },
            },
          }),
        }),
      );
    });

    it("should handle empty results", async () => {
      mockSearch.mockResolvedValueOnce({ hits: { hits: [] } });

      const store = new Elasticsearch(defaultConfig);
      const results = await store.search([0.1, 0.2, 0.3]);

      expect(results).toHaveLength(0);
    });
  });

  describe("get", () => {
    it("should retrieve vector by ID", async () => {
      mockGet.mockResolvedValueOnce({
        _id: "vec-1",
        _source: { metadata: { key: "value" } },
      });

      const store = new Elasticsearch(defaultConfig);
      const result = await store.get("vec-1");

      expect(result).not.toBeNull();
      expect(result?.id).toBe("vec-1");
      expect(result?.payload).toEqual({ key: "value" });
    });

    it("should return null if vector not found", async () => {
      mockGet.mockRejectedValueOnce({
        meta: { statusCode: 404 },
      });

      const store = new Elasticsearch(defaultConfig);
      const result = await store.get("nonexistent");

      expect(result).toBeNull();
    });

    it("should throw error for non-404 errors", async () => {
      mockGet.mockRejectedValueOnce(new Error("Connection failed"));

      const store = new Elasticsearch(defaultConfig);
      await expect(store.get("vec-1")).rejects.toThrow("Connection failed");
    });
  });

  describe("update", () => {
    it("should update vector and payload", async () => {
      mockUpdate.mockResolvedValueOnce({});

      const store = new Elasticsearch(defaultConfig);
      await store.update("vec-1", [0.1, 0.2, 0.3], { updated: true });

      expect(mockUpdate).toHaveBeenCalledWith({
        index: "test-index",
        id: "vec-1",
        doc: {
          vector: [0.1, 0.2, 0.3],
          metadata: { updated: true },
        },
        refresh: true,
      });
    });
  });

  describe("delete", () => {
    it("should delete vector by ID", async () => {
      mockDelete.mockResolvedValueOnce({});

      const store = new Elasticsearch(defaultConfig);
      await store.delete("vec-1");

      expect(mockDelete).toHaveBeenCalledWith({
        index: "test-index",
        id: "vec-1",
        refresh: true,
      });
    });
  });

  describe("deleteCol", () => {
    it("should delete the index", async () => {
      mockIndicesDelete.mockResolvedValueOnce({});

      const store = new Elasticsearch(defaultConfig);
      await store.deleteCol();

      expect(mockIndicesDelete).toHaveBeenCalledWith({
        index: "test-index",
      });
    });
  });

  describe("list", () => {
    it("should list vectors with match_all query", async () => {
      mockSearch.mockResolvedValueOnce({
        hits: {
          hits: [
            { _id: "vec-1", _source: { metadata: { key: "value1" } } },
            { _id: "vec-2", _source: { metadata: { key: "value2" } } },
          ],
        },
      });

      const store = new Elasticsearch(defaultConfig);
      const [results, count] = await store.list(undefined, 100);

      expect(results).toHaveLength(2);
      expect(count).toBe(2);
      expect(results[0].id).toBe("vec-1");
      expect(mockSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          query: { match_all: {} },
          size: 100,
        }),
      );
    });

    it("should apply filters when listing", async () => {
      mockSearch.mockResolvedValueOnce({
        hits: { hits: [] },
      });

      const store = new Elasticsearch(defaultConfig);
      await store.list({ userId: "user1" }, 50);

      expect(mockSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          query: {
            bool: {
              must: [{ term: { "metadata.userId": "user1" } }],
            },
          },
          size: 50,
        }),
      );
    });
  });

  describe("getUserId / setUserId", () => {
    it("should get and set user ID", async () => {
      const store = new Elasticsearch(defaultConfig);

      expect(await store.getUserId()).toBe("");

      await store.setUserId("user-123");
      expect(await store.getUserId()).toBe("user-123");
    });
  });

  describe("close", () => {
    it("should call client close", async () => {
      const store = new Elasticsearch(defaultConfig);
      await store.close();

      expect(mockClose).toHaveBeenCalled();
    });
  });
});
