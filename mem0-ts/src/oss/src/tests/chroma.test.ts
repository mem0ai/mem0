const __mocks__: {
  add: jest.Mock;
  query: jest.Mock;
  get: jest.Mock;
  update: jest.Mock;
  upsert: jest.Mock;
  delete: jest.Mock;
  getOrCreateCollection: jest.Mock;
  deleteCollection: jest.Mock;
  ChromaClient: jest.Mock;
  CloudClient: jest.Mock;
} = {} as any;

jest.mock(
  "chromadb",
  () => {
    const add = jest.fn().mockResolvedValue(undefined);
    const query = jest.fn().mockResolvedValue({
      ids: [[]],
      distances: [[]],
      metadatas: [[]],
    });
    const get = jest.fn().mockResolvedValue({ ids: [], metadatas: [] });
    const update = jest.fn().mockResolvedValue(undefined);
    const upsert = jest.fn().mockResolvedValue(undefined);
    const deleteMock = jest.fn().mockResolvedValue(undefined);

    const collection = { add, query, get, update, upsert, delete: deleteMock };
    const getOrCreateCollection = jest.fn().mockResolvedValue(collection);
    const deleteCollection = jest.fn().mockResolvedValue(undefined);

    const ChromaClient = jest.fn().mockImplementation(() => ({
      getOrCreateCollection,
      deleteCollection,
    }));
    const CloudClient = jest.fn().mockImplementation(() => ({
      getOrCreateCollection,
      deleteCollection,
    }));

    Object.assign(__mocks__, {
      add,
      query,
      get,
      update,
      upsert,
      delete: deleteMock,
      getOrCreateCollection,
      deleteCollection,
      ChromaClient,
      CloudClient,
    });

    return { ChromaClient, CloudClient };
  },
  { virtual: true },
);

import { ChromaDB } from "../vector_stores/chroma";
import { VectorStoreFactory } from "../utils/factory";

function makeDb(overrides: Record<string, any> = {}): ChromaDB {
  return new ChromaDB({
    collectionName: "memories",
    dimension: 4,
    ...overrides,
  } as any);
}

async function initDb(overrides: Record<string, any> = {}): Promise<ChromaDB> {
  const db = makeDb(overrides);
  await db.initialize();
  return db;
}

beforeEach(() => {
  jest.requireMock("chromadb");
  jest.clearAllMocks();
  __mocks__.query.mockResolvedValue({
    ids: [[]],
    distances: [[]],
    metadatas: [[]],
  });
  __mocks__.get.mockResolvedValue({ ids: [], metadatas: [] });
});

describe("VectorStoreFactory", () => {
  it("returns a ChromaDB instance for provider 'chroma'", async () => {
    const db = VectorStoreFactory.create("chroma", {
      collectionName: "memories",
      dimension: 4,
    } as any);
    expect(db).toBeInstanceOf(ChromaDB);
    await db.initialize();
  });
});

describe("ChromaDB", () => {
  it("creates a local Chroma client and collection", async () => {
    await initDb({ host: "localhost", port: 8000, ssl: false });

    expect(__mocks__.ChromaClient).toHaveBeenCalledWith({
      host: "localhost",
      port: 8000,
      ssl: false,
    });
    expect(__mocks__.getOrCreateCollection).toHaveBeenCalledWith({
      name: "memories",
      embeddingFunction: null,
    });
  });

  it("defaults the collection name when omitted", async () => {
    const db = new ChromaDB({ dimension: 4 } as any);
    await db.initialize();

    expect(__mocks__.getOrCreateCollection).toHaveBeenCalledWith({
      name: "memories",
      embeddingFunction: null,
    });
  });

  it("uses CloudClient when apiKey is configured", async () => {
    await initDb({ apiKey: "chroma-key", tenant: "tenant-a" });

    expect(__mocks__.CloudClient).toHaveBeenCalledWith({
      apiKey: "chroma-key",
      tenant: "tenant-a",
      database: "mem0",
    });
    expect(__mocks__.ChromaClient).not.toHaveBeenCalled();
  });

  it("adds vectors with metadata payloads", async () => {
    const db = await initDb();
    await db.insert([[1, 2, 3, 4]], ["vec-1"], [{ text: "hello" }]);

    expect(__mocks__.add).toHaveBeenCalledWith({
      ids: ["vec-1"],
      embeddings: [[1, 2, 3, 4]],
      metadatas: [{ text: "hello" }],
    });
  });

  it("queries by embedding and maps distances to scores", async () => {
    __mocks__.query.mockResolvedValue({
      ids: [["vec-1"]],
      distances: [[0.25]],
      metadatas: [[{ text: "hello" }]],
    });
    const db = await initDb();

    const results = await db.search([1, 2, 3, 4], 3, { user_id: "alice" });

    expect(__mocks__.query).toHaveBeenCalledWith({
      queryEmbeddings: [[1, 2, 3, 4]],
      nResults: 3,
      where: { user_id: { $eq: "alice" } },
      include: ["metadatas", "distances"],
    });
    expect(results).toEqual([
      { id: "vec-1", payload: { text: "hello" }, score: 0.8 },
    ]);
  });

  it("retrieves one vector by id", async () => {
    __mocks__.get.mockResolvedValue({
      ids: ["vec-1"],
      metadatas: [{ text: "hello" }],
    });
    const db = await initDb();

    await expect(db.get("vec-1")).resolves.toEqual({
      id: "vec-1",
      payload: { text: "hello" },
    });
    expect(__mocks__.get).toHaveBeenCalledWith({
      ids: ["vec-1"],
      include: ["metadatas"],
    });
  });

  it("updates and deletes vectors", async () => {
    const db = await initDb();

    await db.update("vec-1", [4, 3, 2, 1], { text: "updated" });
    await db.delete("vec-1");

    expect(__mocks__.update).toHaveBeenCalledWith({
      ids: ["vec-1"],
      embeddings: [[4, 3, 2, 1]],
      metadatas: [{ text: "updated" }],
    });
    expect(__mocks__.delete).toHaveBeenCalledWith({ ids: ["vec-1"] });
  });

  it("lists vectors with filters and returns count", async () => {
    __mocks__.get.mockResolvedValue({
      ids: ["a", "b"],
      metadatas: [{ tag: "x" }, { tag: "x" }],
    });
    const db = await initDb();

    const [results, count] = await db.list({ tag: "x" }, 10);

    expect(__mocks__.get).toHaveBeenCalledWith({
      where: { tag: { $eq: "x" } },
      limit: 10,
      include: ["metadatas"],
    });
    expect(results).toEqual([
      { id: "a", payload: { tag: "x" } },
      { id: "b", payload: { tag: "x" } },
    ]);
    expect(count).toBe(2);
  });

  it("deletes and recreates the collection", async () => {
    const db = await initDb();

    await db.deleteCol();

    expect(__mocks__.deleteCollection).toHaveBeenCalledWith({
      name: "memories",
    });
    const mainCollectionCalls =
      __mocks__.getOrCreateCollection.mock.calls.filter(
        ([args]) => args.name === "memories",
      );
    expect(mainCollectionCalls).toHaveLength(2);
  });

  it("upserts the migrations record when setting user id", async () => {
    const db = await initDb();

    await db.setUserId("user-123");

    expect(__mocks__.upsert).toHaveBeenCalledWith({
      ids: ["mem0-user-id"],
      embeddings: [[0, 0, 0, 0]],
      metadatas: [{ user_id: "user-123" }],
    });
  });

  it("upserts a generated user id when migrations record is missing", async () => {
    __mocks__.get.mockResolvedValue({ ids: [], metadatas: [] });
    const db = await initDb();

    const userId = await db.getUserId();

    expect(typeof userId).toBe("string");
    expect(userId.length).toBeGreaterThan(0);
    expect(__mocks__.upsert).toHaveBeenCalledWith({
      ids: ["mem0-user-id"],
      embeddings: [[0, 0, 0, 0]],
      metadatas: [{ user_id: userId }],
    });
  });
});
