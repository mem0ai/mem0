/// <reference types="jest" />

type MockFn = jest.Mock;

const mockIndicesExists = jest.fn();
const mockIndicesCreate = jest.fn();
const mockBulk = jest.fn();
const mockSearch = jest.fn();
const mockGet = jest.fn();
const mockUpdate = jest.fn();
const mockDelete = jest.fn();
const mockIndicesDelete = jest.fn();
const mockIndex_ = jest.fn();

const mockClient = jest.fn().mockImplementation(() => ({
  indices: {
    exists: mockIndicesExists,
    create: mockIndicesCreate,
    delete: mockIndicesDelete,
  },
  bulk: mockBulk,
  search: mockSearch,
  get: mockGet,
  update: mockUpdate,
  delete: mockDelete,
  index: mockIndex_,
}));

jest.mock("@elastic/elasticsearch", () => ({
  Client: mockClient,
}));

const { ElasticsearchDB } = require("../src/vector_stores/elasticsearch");

beforeEach(() => {
  jest.clearAllMocks();
  mockIndicesExists.mockResolvedValue(false);
  mockIndicesCreate.mockResolvedValue({});
  mockBulk.mockResolvedValue({});
  mockSearch.mockResolvedValue({ hits: { hits: [] } });
  mockGet.mockResolvedValue({
    _id: "test-id",
    _source: { metadata: { key: "val" } },
  });
  mockUpdate.mockResolvedValue({});
  mockDelete.mockResolvedValue({});
  mockIndicesDelete.mockResolvedValue({});
  mockIndex_.mockResolvedValue({ _id: "new-id" });
});

describe("ElasticsearchDB", () => {
  describe("constructor", () => {
    it("creates client with self-hosted host:port", () => {
      new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 768,
        host: "localhost",
        port: 9200,
        username: "user",
        password: "pass",
      });

      expect(mockClient).toHaveBeenCalledWith(
        expect.objectContaining({
          node: "https://localhost:9200",
          auth: { username: "user", password: "pass" },
        }),
      );
    });

    it("creates client with cloud config", () => {
      new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 1536,
        cloudId:
          "my-cloud:dXMtZWFzdDQuZ2NwLmVsYXN0aWMtY2xvdWQuY29tOjQ0MyQxMjM0NTY3ODkw",
        apiKey: "base64-key",
      });

      expect(mockClient).toHaveBeenCalledWith(
        expect.objectContaining({
          cloud: {
            id: "my-cloud:dXMtZWFzdDQuZ2NwLmVsYXN0aWMtY2xvdWQuY29tOjQ0MyQxMjM0NTY3ODkw",
          },
          auth: { apiKey: "base64-key" },
        }),
      );
    });

    it("accepts pre-configured client", () => {
      const preExisting = new mockClient();
      new ElasticsearchDB({
        client: preExisting,
        collectionName: "mem0",
        embeddingModelDims: 1536,
      });

      expect(mockClient).toHaveBeenCalledTimes(1);
    });

    it("defaults to port 9200 and https", () => {
      new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 384,
        host: "es.example.com",
      });

      expect(mockClient).toHaveBeenCalledWith(
        expect.objectContaining({
          node: "https://es.example.com:9200",
        }),
      );
    });
  });

  describe("initialize", () => {
    it("creates index with correct dense_vector mapping", async () => {
      const store = new ElasticsearchDB({
        collectionName: "my_memories",
        embeddingModelDims: 768,
        host: "localhost",
      });

      await store.initialize();

      expect(mockIndicesExists).toHaveBeenCalledWith({ index: "my_memories" });
      expect(mockIndicesCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          index: "my_memories",
          mappings: {
            properties: {
              vector: {
                type: "dense_vector",
                dims: 768,
                index: true,
                similarity: "cosine",
              },
              metadata: {
                type: "object",
                properties: {
                  user_id: { type: "keyword" },
                  agent_id: { type: "keyword" },
                  run_id: { type: "keyword" },
                },
              },
            },
          },
        }),
      );
    });

    it("creates memory_migrations index with dims 1", async () => {
      const store = new ElasticsearchDB({
        collectionName: "test",
        embeddingModelDims: 1536,
        host: "localhost",
      });

      await store.initialize();

      expect(mockIndicesCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          index: "memory_migrations",
          mappings: {
            properties: {
              vector: {
                type: "dense_vector",
                dims: 1,
                index: true,
                similarity: "cosine",
              },
              metadata: {
                type: "object",
                properties: {
                  user_id: { type: "keyword" },
                  agent_id: { type: "keyword" },
                  run_id: { type: "keyword" },
                },
              },
            },
          },
        }),
      );
    });

    it("is idempotent (initialize does not re-run)", async () => {
      const store = new ElasticsearchDB({
        collectionName: "test",
        embeddingModelDims: 1536,
        host: "localhost",
      });

      await store.initialize();

      mockIndicesExists.mockClear();

      await store.initialize();
      expect(mockIndicesExists).not.toHaveBeenCalled();
    });

    it("skips index creation when autoCreateIndex is false", async () => {
      const store = new ElasticsearchDB({
        collectionName: "test",
        embeddingModelDims: 1536,
        host: "localhost",
        autoCreateIndex: false,
      });

      await store.initialize();

      expect(mockIndicesExists).not.toHaveBeenCalledWith({ index: "test" });
    });
  });

  describe("insert", () => {
    it("bulk indexes vectors with ids and payloads", async () => {
      const store = new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 4,
        host: "localhost",
      });

      await store.insert(
        [
          [0.1, 0.2, 0.3, 0.4],
          [0.5, 0.6, 0.7, 0.8],
        ],
        ["id-1", "id-2"],
        [{ user_id: "u1" }, { user_id: "u2" }],
      );

      expect(mockBulk).toHaveBeenCalledWith({
        operations: [
          { index: { _index: "mem0", _id: "id-1" } },
          { vector: [0.1, 0.2, 0.3, 0.4], metadata: { user_id: "u1" } },
          { index: { _index: "mem0", _id: "id-2" } },
          { vector: [0.5, 0.6, 0.7, 0.8], metadata: { user_id: "u2" } },
        ],
      });
    });
  });

  describe("search", () => {
    it("builds correct knn query", async () => {
      mockSearch.mockResolvedValue({
        hits: {
          hits: [
            {
              _id: "id-1",
              _score: 0.95,
              _source: { metadata: { user_id: "u1" } },
            },
          ],
        },
      });

      const store = new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 4,
        host: "localhost",
      });

      const results = await store.search([0.1, 0.2, 0.3, 0.4], 3);

      expect(mockSearch).toHaveBeenCalledWith({
        index: "mem0",
        body: {
          knn: {
            field: "vector",
            query_vector: [0.1, 0.2, 0.3, 0.4],
            k: 3,
            num_candidates: 6,
          },
        },
      });
      expect(results).toEqual([
        { id: "id-1", score: 0.95, payload: { user_id: "u1" } },
      ]);
    });

    it("applies metadata filters", async () => {
      const store = new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 4,
        host: "localhost",
      });

      await store.search([0.1, 0.2, 0.3, 0.4], 5, {
        user_id: "u1",
        agent_id: "a1",
      });

      expect(mockSearch).toHaveBeenCalledWith({
        index: "mem0",
        body: {
          knn: {
            field: "vector",
            query_vector: [0.1, 0.2, 0.3, 0.4],
            k: 5,
            num_candidates: 10,
            filter: {
              bool: {
                must: [
                  { term: { "metadata.user_id": "u1" } },
                  { term: { "metadata.agent_id": "a1" } },
                ],
              },
            },
          },
        },
      });
    });
  });

  describe("get", () => {
    it("returns document by id", async () => {
      const store = new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 4,
        host: "localhost",
      });

      const result = await store.get("id-1");

      expect(mockGet).toHaveBeenCalledWith({ index: "mem0", id: "id-1" });
      expect(result).toEqual({ id: "test-id", payload: { key: "val" } });
    });

    it("returns null on 404", async () => {
      mockGet.mockRejectedValue({ meta: { statusCode: 404 } });

      const store = new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 4,
        host: "localhost",
      });

      const result = await store.get("missing");
      expect(result).toBeNull();
    });
  });

  describe("update", () => {
    it("updates vector and payload", async () => {
      const store = new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 4,
        host: "localhost",
      });

      await store.update("id-1", [1, 2, 3, 4], { key: "val" });

      expect(mockUpdate).toHaveBeenCalledWith({
        index: "mem0",
        id: "id-1",
        doc: { vector: [1, 2, 3, 4], metadata: { key: "val" } },
      });
    });
  });

  describe("delete", () => {
    it("deletes document by id", async () => {
      const store = new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 4,
        host: "localhost",
      });

      await store.delete("id-1");

      expect(mockDelete).toHaveBeenCalledWith({ index: "mem0", id: "id-1" });
    });
  });

  describe("deleteCol", () => {
    it("deletes the index", async () => {
      const store = new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 4,
        host: "localhost",
      });

      await store.deleteCol();

      expect(mockIndicesDelete).toHaveBeenCalledWith({ index: "mem0" });
    });
  });

  describe("list", () => {
    it("returns all documents with count", async () => {
      mockSearch.mockResolvedValue({
        hits: {
          hits: [
            { _id: "a", _source: { metadata: { user_id: "u1" } } },
            { _id: "b", _source: { metadata: { user_id: "u2" } } },
          ],
        },
      });

      const store = new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 4,
        host: "localhost",
      });

      const [results, count] = await store.list();

      expect(mockSearch).toHaveBeenCalledWith({
        index: "mem0",
        body: { query: { match_all: {} }, size: 100 },
      });
      expect(results).toHaveLength(2);
      expect(count).toBe(2);
    });

    it("applies filters to list query", async () => {
      const store = new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 4,
        host: "localhost",
      });

      await store.list({ user_id: "u1" }, 10);

      expect(mockSearch).toHaveBeenCalledWith({
        index: "mem0",
        body: {
          query: { bool: { must: [{ term: { "metadata.user_id": "u1" } }] } },
          size: 10,
        },
      });
    });
  });

  describe("getUserId / setUserId", () => {
    it("generates new userId when memory_migrations is empty", async () => {
      mockSearch.mockResolvedValue({ hits: { hits: [] } });

      const store = new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 4,
        host: "localhost",
      });

      const userId = await store.getUserId();

      expect(mockSearch).toHaveBeenCalledWith({
        index: "memory_migrations",
        body: { query: { match_all: {} }, size: 1 },
      });
      expect(mockIndex_).toHaveBeenCalledWith(
        expect.objectContaining({
          index: "memory_migrations",
          body: expect.objectContaining({
            vector: [0],
            metadata: { user_id: expect.any(String) },
          }),
        }),
      );
      expect(userId).toBeTruthy();
    });

    it("returns existing userId", async () => {
      mockSearch.mockResolvedValue({
        hits: {
          hits: [
            {
              _id: "doc-1",
              _source: { metadata: { user_id: "existing-user" } },
            },
          ],
        },
      });

      const store = new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 4,
        host: "localhost",
      });

      const userId = await store.getUserId();
      expect(userId).toBe("existing-user");
    });

    it("setUserId upserts into memory_migrations", async () => {
      const store = new ElasticsearchDB({
        collectionName: "mem0",
        embeddingModelDims: 4,
        host: "localhost",
      });

      await store.setUserId("custom-user");

      expect(mockIndex_).toHaveBeenCalledWith(
        expect.objectContaining({
          index: "memory_migrations",
          body: { vector: [0], metadata: { user_id: "custom-user" } },
        }),
      );
    });
  });

  describe("factory registration", () => {
    it("is registered in VectorStoreFactory", () => {
      const { VectorStoreFactory } = require("../src/utils/factory");
      const store = VectorStoreFactory.create("elasticsearch", {
        collectionName: "test",
        embeddingModelDims: 128,
        host: "localhost",
        client: new mockClient(),
      });
      expect(store).toBeInstanceOf(ElasticsearchDB);
    });
  });
});
