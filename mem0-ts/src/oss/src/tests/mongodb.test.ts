const mockInsertOne = jest.fn();
const mockDeleteOne = jest.fn();
const mockInsertMany = jest.fn();
const mockFindOne = jest.fn();
const mockUpdateOne = jest.fn();
const mockListSearchIndexes = jest.fn();
const mockCreateSearchIndex = jest.fn();
const mockDrop = jest.fn();
const mockToArray = jest.fn();
const mockLimit = jest.fn().mockReturnThis();
const mockFind = jest.fn().mockReturnValue({
  limit: mockLimit,
  toArray: mockToArray,
});
const mockAggregate = jest.fn().mockReturnValue({
  toArray: mockToArray,
});
const mockListCollections = jest.fn();
const mockClose = jest.fn();

const mockCollection = {
  insertOne: mockInsertOne,
  deleteOne: mockDeleteOne,
  insertMany: mockInsertMany,
  findOne: mockFindOne,
  updateOne: mockUpdateOne,
  listSearchIndexes: mockListSearchIndexes,
  createSearchIndex: mockCreateSearchIndex,
  drop: mockDrop,
  find: mockFind,
  aggregate: mockAggregate,
};

const mockDb = {
  collection: jest.fn().mockReturnValue(mockCollection),
  listCollections: mockListCollections,
};

const mockMongoClient = jest.fn().mockImplementation(() => {
  return {
    db: jest.fn().mockReturnValue(mockDb),
    close: mockClose,
  };
});

jest.mock("mongodb", () => {
  return {
    MongoClient: mockMongoClient,
  };
});

import { MongoDB } from "../vector_stores/mongodb";

describe("MongoDB Vector Store", () => {
  let store: MongoDB;

  beforeEach(() => {
    jest.clearAllMocks();
    mockListCollections.mockReturnValue({
      toArray: jest.fn().mockResolvedValue([]),
    });
    mockListSearchIndexes.mockReturnValue({
      toArray: jest.fn().mockResolvedValue([]),
    });
    store = new MongoDB({
      url: "mongodb://localhost:27017",
      dbName: "test_db",
      collectionName: "test_col",
      embeddingModelDims: 4,
    });
  });

  afterEach(async () => {
    await store.close();
  });

  it("should initialize client and check/create collection and indexes", async () => {
    await store.initialize();

    expect(mockListCollections).toHaveBeenCalledWith({ name: "test_col" });
    expect(mockCollection.insertOne).toHaveBeenCalledWith({
      _id: 0,
      placeholder: true,
    });
    expect(mockCollection.deleteOne).toHaveBeenCalledWith({ _id: 0 });
    expect(mockCreateSearchIndex).toHaveBeenCalledTimes(2);
  });

  it("should insert documents correctly", async () => {
    mockInsertMany.mockResolvedValue({ insertedCount: 2 });

    await store.insert(
      [
        [0.1, 0.2, 0.3, 0.4],
        [0.5, 0.6, 0.7, 0.8],
      ],
      ["id1", "id2"],
      [{ user: "alice" }, { user: "bob" }],
    );

    expect(mockInsertMany).toHaveBeenCalledWith([
      {
        _id: "id1",
        embedding: [0.1, 0.2, 0.3, 0.4],
        payload: { user: "alice" },
      },
      { _id: "id2", embedding: [0.5, 0.6, 0.7, 0.8], payload: { user: "bob" } },
    ]);
  });

  it("should perform vector search correctly without filters", async () => {
    mockListSearchIndexes.mockReturnValue({
      toArray: jest.fn().mockResolvedValue([{ name: "test_col_vector_index" }]),
    });
    mockToArray.mockResolvedValue([
      { _id: "id1", score: 0.95, payload: { text: "hello" } },
      { _id: "id2", score: 0.85, payload: { text: "world" } },
    ]);

    const results = await store.search([0.1, 0.2, 0.3, 0.4], 2);

    expect(results).toEqual([
      { id: "id1", score: 0.95, payload: { text: "hello" } },
      { id: "id2", score: 0.85, payload: { text: "world" } },
    ]);

    expect(mockAggregate).toHaveBeenCalledWith([
      {
        $vectorSearch: {
          index: "test_col_vector_index",
          limit: 2,
          numCandidates: 40,
          queryVector: [0.1, 0.2, 0.3, 0.4],
          path: "embedding",
        },
      },
      { $set: { score: { $meta: "vectorSearchScore" } } },
      { $project: { embedding: 0 } },
    ]);
  });

  it("should perform vector search correctly with filters", async () => {
    mockListSearchIndexes.mockReturnValue({
      toArray: jest.fn().mockResolvedValue([{ name: "test_col_vector_index" }]),
    });
    mockToArray.mockResolvedValue([]);

    await store.search([0.1, 0.2, 0.3, 0.4], 2, {
      user: "alice",
      role: "admin",
    });

    expect(mockAggregate).toHaveBeenCalledWith([
      {
        $vectorSearch: {
          index: "test_col_vector_index",
          limit: 2,
          numCandidates: 40,
          queryVector: [0.1, 0.2, 0.3, 0.4],
          path: "embedding",
        },
      },
      {
        $match: {
          $and: [{ "payload.user": "alice" }, { "payload.role": "admin" }],
        },
      },
      { $set: { score: { $meta: "vectorSearchScore" } } },
      { $project: { embedding: 0 } },
    ]);
  });

  it("should reject invalid object/dict filter values", async () => {
    await expect(
      store.search([0.1, 0.2, 0.3, 0.4], 5, { user: { name: "alice" } }),
    ).rejects.toThrow("Filter value for 'user' must be a scalar");

    await expect(
      store.search([0.1, 0.2, 0.3, 0.4], 5, { user: [{ name: "alice" }] }),
    ).rejects.toThrow("Filter list for 'user' contains an object");
  });

  it("should perform keyword search correctly", async () => {
    mockToArray.mockResolvedValue([
      { _id: "id1", score: 1.5, payload: { data: "test search" } },
    ]);

    const results = await store.keywordSearch("test", 1);

    expect(results).toEqual([
      { id: "id1", score: 1.5, payload: { data: "test search" } },
    ]);

    expect(mockAggregate).toHaveBeenCalledWith([
      {
        $search: {
          index: "test_col_text_search_index",
          text: {
            query: "test",
            path: ["payload.data", "payload.text_lemmatized"],
          },
        },
      },
      { $set: { score: { $meta: "searchScore" } } },
      { $project: { embedding: 0 } },
      { $limit: 1 },
    ]);
  });

  it("should perform get correctly", async () => {
    mockFindOne.mockResolvedValue({
      _id: "id1",
      payload: { data: "get-test" },
    });

    const result = await store.get("id1");
    expect(result).toEqual({ id: "id1", payload: { data: "get-test" } });
    expect(mockFindOne).toHaveBeenCalledWith({ _id: "id1" });
  });

  it("should return null when get document does not exist", async () => {
    mockFindOne.mockResolvedValue(null);

    const result = await store.get("id-non-existent");
    expect(result).toBeNull();
  });

  it("should update document correctly", async () => {
    mockUpdateOne.mockResolvedValue({ matchedCount: 1 });

    await store.update("id1", [0.1, 0.2, 0.3, 0.4], { name: "new-alice" });

    expect(mockUpdateOne).toHaveBeenCalledWith(
      { _id: "id1" },
      {
        $set: {
          embedding: [0.1, 0.2, 0.3, 0.4],
          "payload.name": "new-alice",
        },
      },
    );
  });

  it("should delete document correctly", async () => {
    mockDeleteOne.mockResolvedValue({ deletedCount: 1 });

    await store.delete("id1");

    expect(mockDeleteOne).toHaveBeenCalledWith({ _id: "id1" });
  });

  it("should delete collection correctly", async () => {
    mockDrop.mockResolvedValue(true);

    await store.deleteCol();

    expect(mockDrop).toHaveBeenCalled();
  });

  it("should list documents correctly with filters", async () => {
    mockToArray.mockResolvedValue([{ _id: "id1", payload: { user: "alice" } }]);

    const [results, count] = await store.list({ user: "alice" }, 10);

    expect(results).toEqual([{ id: "id1", payload: { user: "alice" } }]);
    expect(count).toBe(1);
    expect(mockFind).toHaveBeenCalledWith({
      $and: [{ "payload.user": "alice" }],
    });
    expect(mockLimit).toHaveBeenCalledWith(10);
  });

  it("should manage user ID correctly", async () => {
    mockFindOne.mockResolvedValue(null);
    mockUpdateOne.mockResolvedValue({});

    const userId1 = await store.getUserId();
    expect(userId1).toBeDefined();
    expect(typeof userId1).toBe("string");

    mockFindOne.mockResolvedValue({ user_id: "custom-user-123" });
    const userId2 = await store.getUserId();
    expect(userId2).toBe("custom-user-123");

    await store.setUserId("new-custom-user");
    expect(mockUpdateOne).toHaveBeenCalledWith(
      {},
      { $set: { user_id: "new-custom-user" } },
      { upsert: true },
    );
  });
});
