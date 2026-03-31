import { MilvusDB } from "../vector_stores/milvus";

const mockInsert = jest.fn().mockResolvedValue({ succ_count: 1 });
const mockSearch = jest.fn().mockResolvedValue({ results: [] });
const mockGet = jest.fn().mockResolvedValue({ data: [] });
const mockUpsert = jest.fn().mockResolvedValue({ succ_count: 1 });
const mockDelete = jest.fn().mockResolvedValue({ succ_count: 1 });
const mockDropCollection = jest.fn().mockResolvedValue({});
const mockQuery = jest.fn().mockResolvedValue({ data: [] });
const mockHasCollection = jest.fn().mockResolvedValue({ value: true });
const mockCreateCollection = jest.fn().mockResolvedValue({});

jest.mock("@zilliz/milvus2-sdk-node", () => ({
  MilvusClient: jest.fn().mockImplementation(() => ({
    insert: mockInsert,
    search: mockSearch,
    get: mockGet,
    upsert: mockUpsert,
    delete: mockDelete,
    dropCollection: mockDropCollection,
    query: mockQuery,
    hasCollection: mockHasCollection,
    createCollection: mockCreateCollection,
  })),
  DataType: {
    FloatVector: 101,
    VarChar: 21,
    JSON: 23,
  },
}));

describe("MilvusDB", () => {
  let db: MilvusDB;

  beforeEach(() => {
    jest.clearAllMocks();
    mockHasCollection.mockResolvedValue({ value: true });

    db = new MilvusDB({
      url: "localhost:19530",
      collectionName: "test_collection",
      embeddingModelDims: 1536,
    });
  });

  describe("constructor", () => {
    it("should create MilvusDB with default config", () => {
      expect(db).toBeInstanceOf(MilvusDB);
    });

    it("should accept a pre-configured client", () => {
      const customClient = {
        insert: jest.fn(),
        search: jest.fn(),
        get: jest.fn(),
        upsert: jest.fn(),
        delete: jest.fn(),
        dropCollection: jest.fn(),
        query: jest.fn(),
        hasCollection: jest.fn().mockResolvedValue({ value: true }),
        createCollection: jest.fn(),
      };
      const dbWithClient = new MilvusDB({
        client: customClient as any,
        collectionName: "custom_col",
      });
      expect(dbWithClient).toBeInstanceOf(MilvusDB);
    });
  });

  describe("insert", () => {
    it("should insert vectors with ids and payloads", async () => {
      await db.insert(
        [[0.1, 0.2, 0.3]],
        ["id-1"],
        [{ user_id: "alice", data: "likes tea" }],
      );

      expect(mockInsert).toHaveBeenCalledWith({
        collection_name: "test_collection",
        data: [
          {
            id: "id-1",
            vectors: [0.1, 0.2, 0.3],
            metadata: { user_id: "alice", data: "likes tea" },
          },
        ],
      });
    });

    it("should handle batch insert of multiple vectors", async () => {
      await db.insert(
        [
          [0.1, 0.2],
          [0.3, 0.4],
        ],
        ["id-1", "id-2"],
        [{ data: "first" }, { data: "second" }],
      );

      expect(mockInsert).toHaveBeenCalledWith({
        collection_name: "test_collection",
        data: [
          { id: "id-1", vectors: [0.1, 0.2], metadata: { data: "first" } },
          { id: "id-2", vectors: [0.3, 0.4], metadata: { data: "second" } },
        ],
      });
    });

    it("should use empty object for missing payloads", async () => {
      const payloads: Record<string, any>[] = [];
      await db.insert([[0.1]], ["id-1"], payloads);

      expect(mockInsert).toHaveBeenCalledWith({
        collection_name: "test_collection",
        data: [{ id: "id-1", vectors: [0.1], metadata: {} }],
      });
    });
  });

  describe("search", () => {
    it("should return empty array when no results", async () => {
      mockSearch.mockResolvedValueOnce({ results: [] });

      const results = await db.search([0.1, 0.2, 0.3], 5);
      expect(results).toEqual([]);
    });

    it("should return mapped results with scores", async () => {
      mockSearch.mockResolvedValueOnce({
        results: [
          { id: "id-1", metadata: { data: "likes tea" }, score: 0.95 },
          { id: "id-2", metadata: { data: "likes coffee" }, score: 0.8 },
        ],
      });

      const results = await db.search([0.1, 0.2, 0.3], 5);

      expect(results).toEqual([
        { id: "id-1", payload: { data: "likes tea" }, score: 0.95 },
        { id: "id-2", payload: { data: "likes coffee" }, score: 0.8 },
      ]);
    });

    it("should pass filters as Milvus filter string", async () => {
      mockSearch.mockResolvedValueOnce({ results: [] });

      await db.search([0.1], 5, { user_id: "alice" });

      expect(mockSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          filter: '(metadata["user_id"] == "alice")',
        }),
      );
    });

    it("should combine multiple filters with 'and'", async () => {
      mockSearch.mockResolvedValueOnce({ results: [] });

      await db.search([0.1], 5, { user_id: "alice", agent_id: "bot1" });

      const callArgs = mockSearch.mock.calls[0][0];
      expect(callArgs.filter).toContain('metadata["user_id"] == "alice"');
      expect(callArgs.filter).toContain('metadata["agent_id"] == "bot1"');
      expect(callArgs.filter).toContain(" and ");
    });

    it("should handle numeric filter values without quotes", async () => {
      mockSearch.mockResolvedValueOnce({ results: [] });

      await db.search([0.1], 5, { score: 42 } as any);

      expect(mockSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          filter: '(metadata["score"] == 42)',
        }),
      );
    });

    it("should use distance as fallback score", async () => {
      mockSearch.mockResolvedValueOnce({
        results: [{ id: "id-1", metadata: { data: "test" }, distance: 0.12 }],
      });

      const results = await db.search([0.1], 5);
      expect(results[0].score).toBe(0.12);
    });
  });

  describe("get", () => {
    it("should return null when vector not found", async () => {
      mockGet.mockResolvedValueOnce({ data: [] });

      const result = await db.get("nonexistent-id");
      expect(result).toBeNull();
    });

    it("should return vector with payload when found", async () => {
      mockGet.mockResolvedValueOnce({
        data: [{ id: "id-1", metadata: { data: "likes tea" } }],
      });

      const result = await db.get("id-1");
      expect(result).toEqual({
        id: "id-1",
        payload: { data: "likes tea" },
      });
    });
  });

  describe("update", () => {
    it("should upsert with new vector and payload", async () => {
      await db.update("id-1", [0.5, 0.6], { data: "updated memory" });

      expect(mockUpsert).toHaveBeenCalledWith({
        collection_name: "test_collection",
        data: [
          {
            id: "id-1",
            vectors: [0.5, 0.6],
            metadata: { data: "updated memory" },
          },
        ],
      });
    });
  });

  describe("delete", () => {
    it("should delete a vector by id", async () => {
      await db.delete("id-1");

      expect(mockDelete).toHaveBeenCalledWith({
        collection_name: "test_collection",
        ids: ["id-1"],
      });
    });
  });

  describe("deleteCol", () => {
    it("should drop the collection", async () => {
      await db.deleteCol();

      expect(mockDropCollection).toHaveBeenCalledWith({
        collection_name: "test_collection",
      });
    });
  });

  describe("list", () => {
    it("should return empty results when collection is empty", async () => {
      mockQuery.mockResolvedValueOnce({ data: [] });

      const [results, count] = await db.list();
      expect(results).toEqual([]);
      expect(count).toBe(0);
    });

    it("should return formatted results with count", async () => {
      mockQuery.mockResolvedValueOnce({
        data: [
          { id: "id-1", metadata: { data: "memory one" } },
          { id: "id-2", metadata: { data: "memory two" } },
        ],
      });

      const [results, count] = await db.list();
      expect(count).toBe(2);
      expect(results).toEqual([
        { id: "id-1", payload: { data: "memory one" } },
        { id: "id-2", payload: { data: "memory two" } },
      ]);
    });

    it("should pass filters and limit to query", async () => {
      mockQuery.mockResolvedValueOnce({ data: [] });

      await db.list({ user_id: "alice" }, 50);

      expect(mockQuery).toHaveBeenCalledWith(
        expect.objectContaining({
          collection_name: "test_collection",
          filter: '(metadata["user_id"] == "alice")',
          limit: 50,
        }),
      );
    });
  });

  describe("getUserId", () => {
    it("should return existing user ID from migrations collection", async () => {
      mockQuery.mockResolvedValueOnce({
        data: [{ metadata: { user_id: "existing-user-123" } }],
      });

      const userId = await db.getUserId();
      expect(userId).toBe("existing-user-123");
    });

    it("should generate and store a new user ID if none exists", async () => {
      mockQuery.mockResolvedValueOnce({ data: [] });
      mockInsert.mockResolvedValueOnce({ succ_count: 1 });

      const userId = await db.getUserId();
      expect(typeof userId).toBe("string");
      expect(userId.length).toBeGreaterThan(0);
      expect(mockInsert).toHaveBeenCalledWith(
        expect.objectContaining({
          collection_name: "memory_migrations",
        }),
      );
    });
  });

  describe("setUserId", () => {
    it("should upsert user ID into migrations collection", async () => {
      mockQuery.mockResolvedValueOnce({
        data: [{ id: "existing-point-id" }],
      });

      await db.setUserId("new-user-456");

      expect(mockUpsert).toHaveBeenCalledWith({
        collection_name: "memory_migrations",
        data: [
          expect.objectContaining({
            id: "existing-point-id",
            metadata: { user_id: "new-user-456" },
          }),
        ],
      });
    });

    it("should create a new point if none exists", async () => {
      mockQuery.mockResolvedValueOnce({ data: [] });

      await db.setUserId("brand-new-user");

      expect(mockUpsert).toHaveBeenCalledWith({
        collection_name: "memory_migrations",
        data: [
          expect.objectContaining({
            metadata: { user_id: "brand-new-user" },
          }),
        ],
      });
    });
  });

  describe("initialize", () => {
    it("should create collection when it does not exist", async () => {
      mockHasCollection.mockResolvedValue({ value: false });

      const freshDb = new MilvusDB({
        url: "localhost:19530",
        collectionName: "new_collection",
        embeddingModelDims: 768,
      });

      await freshDb.initialize();

      expect(mockCreateCollection).toHaveBeenCalledWith(
        expect.objectContaining({
          collection_name: "new_collection",
        }),
      );
    });

    it("should skip creation when collection already exists", async () => {
      mockHasCollection.mockResolvedValue({ value: true });
      mockCreateCollection.mockClear();

      const freshDb = new MilvusDB({
        url: "localhost:19530",
        collectionName: "existing_collection",
      });

      await freshDb.initialize();

      expect(mockCreateCollection).not.toHaveBeenCalled();
    });
  });
});

describe("VectorStoreFactory integration", () => {
  it("should create MilvusDB via factory with 'milvus' provider", () => {
    const { VectorStoreFactory } = require("../utils/factory");
    mockHasCollection.mockResolvedValue({ value: true });

    const store = VectorStoreFactory.create("milvus", {
      url: "localhost:19530",
      collectionName: "factory_test",
      embeddingModelDims: 1536,
    });

    expect(store).toBeInstanceOf(MilvusDB);
  });
});
