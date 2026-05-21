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
const mockDescribeCollection = jest.fn().mockResolvedValue({ fields: [] });

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
    describeCollection: mockDescribeCollection,
  })),
  DataType: {
    FloatVector: 101,
    VarChar: 21,
    JSON: 23,
    SparseFloatVector: 104,
  },
  FunctionType: {
    BM25: 1,
  },
}));

async function createBm25Db(
  collectionName: string = "bm25_col",
): Promise<MilvusDB> {
  jest.clearAllMocks();
  mockHasCollection.mockResolvedValue({ value: true });
  mockDescribeCollection.mockResolvedValue({
    fields: [
      { name: "id" },
      { name: "vectors" },
      { name: "metadata" },
      { name: "text" },
      { name: "sparse" },
    ],
  });

  const freshDb = new MilvusDB({
    url: "localhost:19530",
    collectionName,
  });
  await freshDb.initialize();
  mockInsert.mockClear();
  mockUpsert.mockClear();
  mockSearch.mockClear();
  return freshDb;
}

describe("MilvusDB", () => {
  let db: MilvusDB;
  let warnSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    warnSpy = jest.spyOn(console, "warn").mockImplementation();
    mockHasCollection.mockResolvedValue({ value: true });
    mockDescribeCollection.mockResolvedValue({ fields: [] });

    db = new MilvusDB({
      url: "localhost:19530",
      collectionName: "test_collection",
      embeddingModelDims: 1536,
    });
  });

  afterEach(() => {
    warnSpy.mockRestore();
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
        describeCollection: jest.fn().mockResolvedValue({ fields: [] }),
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

    it("should escape double quotes in filter string values", async () => {
      mockSearch.mockResolvedValueOnce({ results: [] });

      await db.search([0.1], 5, { user_id: 'alice" OR 1==1 --' } as any);

      expect(mockSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          filter: '(metadata["user_id"] == "alice\\" OR 1==1 --")',
        }),
      );
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
      mockDescribeCollection.mockResolvedValue({ fields: [] });
      mockCreateCollection.mockClear();

      const freshDb = new MilvusDB({
        url: "localhost:19530",
        collectionName: "existing_collection",
      });

      await freshDb.initialize();

      expect(mockCreateCollection).not.toHaveBeenCalled();
    });

    it("should propagate custom metricType to vector index", async () => {
      mockHasCollection.mockResolvedValue({ value: false });

      const freshDb = new MilvusDB({
        url: "localhost:19530",
        collectionName: "metric_test_col",
        embeddingModelDims: 768,
        metricType: "L2",
      });

      await freshDb.initialize();

      const mainColCall = mockCreateCollection.mock.calls.find(
        (call) => call[0].collection_name === "metric_test_col",
      );
      expect(mainColCall).toBeDefined();
      const vectorIndex = mainColCall[0].index_params.find(
        (ip: any) => ip.field_name === "vectors",
      );
      expect(vectorIndex.metric_type).toBe("L2");
    });

    it("should warn when existing collection lacks BM25 schema", async () => {
      warnSpy.mockClear();
      mockHasCollection.mockResolvedValue({ value: true });
      mockDescribeCollection.mockResolvedValue({
        fields: [{ name: "id" }, { name: "vectors" }, { name: "metadata" }],
      });

      const freshDb = new MilvusDB({
        url: "localhost:19530",
        collectionName: "legacy_warn_col",
      });

      await freshDb.initialize();

      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining("predates v3 hybrid search"),
      );
    });
  });

  describe("BM25 schema", () => {
    it("should add text and sparse fields when creating a new main collection", async () => {
      mockHasCollection.mockResolvedValue({ value: false });

      const freshDb = new MilvusDB({
        url: "localhost:19530",
        collectionName: "new_bm25_collection",
        embeddingModelDims: 768,
      });

      await freshDb.initialize();

      // Find the createCollection call for the main collection
      const mainColCall = mockCreateCollection.mock.calls.find(
        (call) => call[0].collection_name === "new_bm25_collection",
      );
      expect(mainColCall).toBeDefined();
      const fields = mainColCall[0].fields;
      const fieldNames = fields.map((f: any) => f.name);
      expect(fieldNames).toContain("text");
      expect(fieldNames).toContain("sparse");
    });

    it("should NOT add text and sparse fields to the migration collection", async () => {
      mockHasCollection.mockResolvedValue({ value: false });

      const freshDb = new MilvusDB({
        url: "localhost:19530",
        collectionName: "main_col",
        embeddingModelDims: 768,
      });

      await freshDb.initialize();

      const migrationCall = mockCreateCollection.mock.calls.find(
        (call) => call[0].collection_name === "memory_migrations",
      );
      expect(migrationCall).toBeDefined();
      const fields = migrationCall[0].fields;
      const fieldNames = fields.map((f: any) => f.name);
      expect(fieldNames).not.toContain("text");
      expect(fieldNames).not.toContain("sparse");
    });

    it("should add sparse index when creating new main collection", async () => {
      mockHasCollection.mockResolvedValue({ value: false });

      const freshDb = new MilvusDB({
        url: "localhost:19530",
        collectionName: "bm25_idx_col",
        embeddingModelDims: 768,
      });

      await freshDb.initialize();

      const mainColCall = mockCreateCollection.mock.calls.find(
        (call) => call[0].collection_name === "bm25_idx_col",
      );
      const indexParams = mainColCall[0].index_params;
      const sparseIndex = indexParams.find(
        (ip: any) => ip.field_name === "sparse",
      );
      expect(sparseIndex).toBeDefined();
      expect(sparseIndex.index_type).toBe("SPARSE_INVERTED_INDEX");
      expect(sparseIndex.metric_type).toBe("BM25");
    });

    it("should pass BM25 function to createCollection for main collection", async () => {
      mockHasCollection.mockResolvedValue({ value: false });

      const freshDb = new MilvusDB({
        url: "localhost:19530",
        collectionName: "bm25_func_col",
        embeddingModelDims: 768,
      });

      await freshDb.initialize();

      const mainColCall = mockCreateCollection.mock.calls.find(
        (call) => call[0].collection_name === "bm25_func_col",
      );
      expect(mainColCall[0].functions).toBeDefined();
      expect(mainColCall[0].functions).toHaveLength(1);
      expect(mainColCall[0].functions[0].name).toBe("bm25");
      expect(mainColCall[0].functions[0].type).toBe(1); // FunctionType.BM25
      expect(mainColCall[0].functions[0].input_field_names).toEqual(["text"]);
      expect(mainColCall[0].functions[0].output_field_names).toEqual([
        "sparse",
      ]);
    });

    it("should set enable_analyzer on text field", async () => {
      mockHasCollection.mockResolvedValue({ value: false });

      const freshDb = new MilvusDB({
        url: "localhost:19530",
        collectionName: "bm25_analyzer_col",
        embeddingModelDims: 768,
      });

      await freshDb.initialize();

      const mainColCall = mockCreateCollection.mock.calls.find(
        (call) => call[0].collection_name === "bm25_analyzer_col",
      );
      const textField = mainColCall[0].fields.find(
        (f: any) => f.name === "text",
      );
      expect(textField.enable_analyzer).toBe(true);
    });

    it("should NOT pass functions to migration collection", async () => {
      mockHasCollection.mockResolvedValue({ value: false });

      const freshDb = new MilvusDB({
        url: "localhost:19530",
        collectionName: "main_no_func",
        embeddingModelDims: 768,
      });

      await freshDb.initialize();

      const migrationCall = mockCreateCollection.mock.calls.find(
        (call) => call[0].collection_name === "memory_migrations",
      );
      expect(
        migrationCall[0].functions === undefined ||
          migrationCall[0].functions?.length === 0,
      ).toBe(true);
    });

    it("should set _hasBm25Schema when existing collection has text and sparse fields", async () => {
      jest.clearAllMocks();
      mockHasCollection.mockResolvedValue({ value: true });
      mockDescribeCollection.mockResolvedValue({
        fields: [
          { name: "id" },
          { name: "vectors" },
          { name: "metadata" },
          { name: "text" },
          { name: "sparse" },
        ],
      });

      const freshDb = new MilvusDB({
        url: "localhost:19530",
        collectionName: "v3_collection",
      });

      await freshDb.initialize();

      // keywordSearch returns null when _hasBm25Schema is false, non-null when true
      mockSearch.mockResolvedValueOnce({ results: [] });
      const result = await freshDb.keywordSearch("test query");
      expect(result).not.toBeNull();
    });

    it("should NOT set _hasBm25Schema when existing collection lacks text/sparse fields", async () => {
      jest.clearAllMocks();
      mockHasCollection.mockResolvedValue({ value: true });
      mockDescribeCollection.mockResolvedValue({
        fields: [{ name: "id" }, { name: "vectors" }, { name: "metadata" }],
      });

      const freshDb = new MilvusDB({
        url: "localhost:19530",
        collectionName: "legacy_collection",
      });

      await freshDb.initialize();

      const result = await freshDb.keywordSearch("test query");
      expect(result).toBeNull();
    });
  });

  describe("insert with BM25 schema", () => {
    it("should include text field from textLemmatized when BM25 schema exists", async () => {
      const bm25Db = await createBm25Db();

      await bm25Db.insert(
        [[0.1, 0.2]],
        ["id-1"],
        [{ textLemmatized: "lemmatized text here", data: "raw data" }],
      );

      expect(mockInsert).toHaveBeenCalledWith({
        collection_name: "bm25_col",
        data: [
          expect.objectContaining({
            text: "lemmatized text here",
          }),
        ],
      });
    });

    it("should fall back to data field when textLemmatized is absent", async () => {
      const bm25Db = await createBm25Db();

      await bm25Db.insert(
        [[0.1, 0.2]],
        ["id-1"],
        [{ data: "fallback data text" }],
      );

      expect(mockInsert).toHaveBeenCalledWith({
        collection_name: "bm25_col",
        data: [
          expect.objectContaining({
            text: "fallback data text",
          }),
        ],
      });
    });

    it("should NOT include text field when BM25 schema is absent", async () => {
      // db from beforeEach has _hasBm25Schema = false (describeCollection returns no fields)
      await db.insert([[0.1, 0.2]], ["id-1"], [{ data: "some data" }]);

      const callData = mockInsert.mock.calls[0][0].data[0];
      expect(callData).not.toHaveProperty("text");
    });

    it("should truncate text field at 65535 characters", async () => {
      const bm25Db = await createBm25Db();

      const longText = "a".repeat(70000);
      await bm25Db.insert([[0.1]], ["id-1"], [{ data: longText }]);

      const callData = mockInsert.mock.calls[0][0].data[0];
      expect(callData.text.length).toBe(65535);
    });
  });

  describe("update with BM25 schema", () => {
    it("should include text field from textLemmatized in update when BM25 schema exists", async () => {
      const bm25Db = await createBm25Db();

      await bm25Db.update("id-1", [0.5, 0.6], {
        textLemmatized: "lemmatized update",
        data: "raw update",
      });

      expect(mockUpsert).toHaveBeenCalledWith({
        collection_name: "bm25_col",
        data: [
          expect.objectContaining({
            text: "lemmatized update",
          }),
        ],
      });
    });

    it("should fall back to data field in update when textLemmatized absent", async () => {
      const bm25Db = await createBm25Db();

      await bm25Db.update("id-1", [0.5, 0.6], { data: "update data text" });

      expect(mockUpsert).toHaveBeenCalledWith({
        collection_name: "bm25_col",
        data: [
          expect.objectContaining({
            text: "update data text",
          }),
        ],
      });
    });

    it("should NOT include text field in update when BM25 schema is absent", async () => {
      // db from beforeEach has _hasBm25Schema = false
      await db.update("id-1", [0.5, 0.6], { data: "updated memory" });

      const callData = mockUpsert.mock.calls[0][0].data[0];
      expect(callData).not.toHaveProperty("text");
    });
  });

  describe("keywordSearch", () => {
    it("should return null when BM25 schema is absent", async () => {
      // db from beforeEach has _hasBm25Schema = false
      const result = await db.keywordSearch("search query");
      expect(result).toBeNull();
    });

    it("should search the sparse field when BM25 schema exists", async () => {
      const bm25Db = await createBm25Db("bm25_search_col");

      mockSearch.mockResolvedValueOnce({
        results: [{ id: "id-1", metadata: { data: "result one" }, score: 0.9 }],
      });

      const results = await bm25Db.keywordSearch("find memories", 5);

      expect(mockSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          anns_field: "sparse",
          data: ["find memories"],
        }),
      );
      expect(results).toEqual([
        { id: "id-1", payload: { data: "result one" }, score: 0.9 },
      ]);
    });

    it("should pass filters to keyword search", async () => {
      const bm25Db = await createBm25Db("bm25_filter_col");

      mockSearch.mockResolvedValueOnce({ results: [] });

      await bm25Db.keywordSearch("query", 5, { user_id: "alice" });

      expect(mockSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          filter: '(metadata["user_id"] == "alice")',
          anns_field: "sparse",
        }),
      );
    });

    it("should return null on search error (graceful degradation)", async () => {
      const bm25Db = await createBm25Db("bm25_err_col");

      warnSpy.mockClear();
      mockSearch.mockRejectedValueOnce(new Error("Milvus connection error"));

      const result = await bm25Db.keywordSearch("broken query");
      expect(result).toBeNull();
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining("Keyword search not available"),
        expect.any(Error),
      );
    });

    it("should return empty array when search returns no results", async () => {
      const bm25Db = await createBm25Db("bm25_empty_col");

      mockSearch.mockResolvedValueOnce({ results: [] });

      const results = await bm25Db.keywordSearch("no matches");
      expect(results).toEqual([]);
    });
  });

  describe("search with anns_field when BM25 schema exists", () => {
    it("should pass anns_field: vectors when BM25 schema is active", async () => {
      const bm25Db = await createBm25Db("bm25_anns_col");

      mockSearch.mockResolvedValueOnce({ results: [] });

      await bm25Db.search([0.1, 0.2, 0.3], 5);

      expect(mockSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          anns_field: "vectors",
        }),
      );
    });

    it("should NOT pass anns_field when BM25 schema is absent", async () => {
      // db from beforeEach has _hasBm25Schema = false
      mockSearch.mockResolvedValueOnce({ results: [] });

      await db.search([0.1, 0.2, 0.3], 5);

      const callArgs = mockSearch.mock.calls[0][0];
      expect(callArgs).not.toHaveProperty("anns_field");
    });
  });
});

describe("VectorStoreFactory integration", () => {
  it("should create MilvusDB via factory with 'milvus' provider", () => {
    const { VectorStoreFactory } = require("../utils/factory");
    mockHasCollection.mockResolvedValue({ value: true });
    mockDescribeCollection.mockResolvedValue({ fields: [] });

    const store = VectorStoreFactory.create("milvus", {
      url: "localhost:19530",
      collectionName: "factory_test",
      embeddingModelDims: 1536,
    });

    expect(store).toBeInstanceOf(MilvusDB);
  });
});
