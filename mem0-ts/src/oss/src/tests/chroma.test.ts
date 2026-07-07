// jest.mock is hoisted before variable declarations, so we cannot close over
// variables declared with let/const. All shared mock functions are attached to
// the module-level `__mocks__` object that is populated inside the factory so
// that the hoisted mock can reach them via a stable reference.

const __mocks__: {
  add: jest.Mock;
  get: jest.Mock;
  query: jest.Mock;
  update: jest.Mock;
  delete: jest.Mock;
  getOrCreateCollection: jest.Mock;
  deleteCollection: jest.Mock;
  ChromaClient: jest.Mock;
  CloudClient: jest.Mock;
} = {} as any;

jest.mock("chromadb", () => {
  const add = jest.fn().mockResolvedValue(undefined);
  const get = jest.fn().mockResolvedValue({
    ids: [],
    documents: [],
    embeddings: [],
    metadatas: [],
    uris: [],
    include: [],
  });
  const query = jest.fn().mockResolvedValue({
    ids: [[]],
    distances: [[]],
    documents: [[]],
    embeddings: [[]],
    metadatas: [[]],
    uris: [[]],
    include: [],
  });
  const update = jest.fn().mockResolvedValue(undefined);
  const deleteFn = jest.fn().mockResolvedValue(undefined);

  const collectionHandle = { add, get, query, update, delete: deleteFn };
  const getOrCreateCollection = jest.fn().mockResolvedValue(collectionHandle);
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
    get,
    query,
    update,
    delete: deleteFn,
    getOrCreateCollection,
    deleteCollection,
    ChromaClient,
    CloudClient,
  });

  return { ChromaClient, CloudClient };
});

import { ChromaDB } from "../vector_stores/chroma";
import { VectorStoreFactory } from "../utils/factory";

// --- Helpers ---

function makeDb(overrides: Record<string, any> = {}): ChromaDB {
  return new ChromaDB({
    collectionName: "test-collection",
    embeddingModelDims: 4,
    ...overrides,
  } as any);
}

async function initDb(overrides: Record<string, any> = {}): Promise<ChromaDB> {
  const db = makeDb(overrides);
  await db.initialize();
  return db;
}

// --- Reset mocks between tests ---

beforeEach(() => {
  jest.clearAllMocks();

  const collectionHandle = {
    add: __mocks__.add,
    get: __mocks__.get,
    query: __mocks__.query,
    update: __mocks__.update,
    delete: __mocks__.delete,
  };

  __mocks__.add.mockResolvedValue(undefined);
  __mocks__.get.mockResolvedValue({
    ids: [],
    documents: [],
    embeddings: [],
    metadatas: [],
    uris: [],
    include: [],
  });
  __mocks__.query.mockResolvedValue({
    ids: [[]],
    distances: [[]],
    documents: [[]],
    embeddings: [[]],
    metadatas: [[]],
    uris: [[]],
    include: [],
  });
  __mocks__.update.mockResolvedValue(undefined);
  __mocks__.delete.mockResolvedValue(undefined);
  __mocks__.getOrCreateCollection.mockResolvedValue(collectionHandle);
  __mocks__.deleteCollection.mockResolvedValue(undefined);
  __mocks__.ChromaClient.mockImplementation(() => ({
    getOrCreateCollection: __mocks__.getOrCreateCollection,
    deleteCollection: __mocks__.deleteCollection,
  }));
  __mocks__.CloudClient.mockImplementation(() => ({
    getOrCreateCollection: __mocks__.getOrCreateCollection,
    deleteCollection: __mocks__.deleteCollection,
  }));
});

// --- Test suites ---

describe("VectorStoreFactory", () => {
  it("returns a ChromaDB instance for provider 'chroma'", async () => {
    const db = VectorStoreFactory.create("chroma", {
      collectionName: "x",
      embeddingModelDims: 4,
    } as any);
    expect(db).toBeInstanceOf(ChromaDB);
    await (db as any).initialize();
  });
});

describe("Constructor", () => {
  it("creates a local ChromaClient by default", async () => {
    await initDb({ host: "localhost", port: 8000 });
    expect(__mocks__.ChromaClient).toHaveBeenCalledWith(
      expect.objectContaining({ host: "localhost", port: 8000 }),
    );
  });

  it("creates a CloudClient when apiKey and tenant are provided", async () => {
    await initDb({ apiKey: "key", tenant: "tenant-1" });
    expect(__mocks__.CloudClient).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: "key",
        tenant: "tenant-1",
        database: "mem0",
      }),
    );
    expect(__mocks__.ChromaClient).not.toHaveBeenCalled();
  });

  it("accepts a pre-built client via config.client", async () => {
    const fakeClient = {
      getOrCreateCollection: __mocks__.getOrCreateCollection,
      deleteCollection: __mocks__.deleteCollection,
    };
    await initDb({ client: fakeClient });
    expect(__mocks__.ChromaClient).not.toHaveBeenCalled();
    expect(__mocks__.CloudClient).not.toHaveBeenCalled();
    expect(__mocks__.getOrCreateCollection).toHaveBeenCalled();
  });
});

describe("initialize", () => {
  it("creates both the main collection and the migrations collection, disabling the default embedding function", async () => {
    await initDb();
    expect(__mocks__.getOrCreateCollection).toHaveBeenCalledWith({
      name: "test-collection",
      embeddingFunction: null,
    });
    expect(__mocks__.getOrCreateCollection).toHaveBeenCalledWith({
      name: "__mem0_migrations__",
      embeddingFunction: null,
    });
  });

  it("_initPromise is shared across concurrent calls (idempotent)", async () => {
    const db = makeDb();
    await Promise.all([db.initialize(), db.initialize(), db.initialize()]);
    expect(__mocks__.getOrCreateCollection).toHaveBeenCalledTimes(2);
  });
});

describe("insert", () => {
  it("adds records with correct shape", async () => {
    const db = await initDb();
    await db.insert([[1, 2, 3, 4]], ["id-1"], [{ text: "hello" }]);
    expect(__mocks__.add).toHaveBeenCalledWith({
      ids: ["id-1"],
      embeddings: [[1, 2, 3, 4]],
      metadatas: [{ text: "hello" }],
    });
  });
});

describe("search", () => {
  it("calls query with correct args", async () => {
    const db = await initDb();
    await db.search([1, 2, 3, 4], 10);
    expect(__mocks__.query).toHaveBeenCalledWith(
      expect.objectContaining({
        queryEmbeddings: [[1, 2, 3, 4]],
        nResults: 10,
      }),
    );
  });

  it("translates equality filter to Chroma $eq", async () => {
    const db = await initDb();
    await db.search([1, 2, 3, 4], 5, { user_id: "alice" });
    expect(__mocks__.query).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { user_id: { $eq: "alice" } },
      }),
    );
  });

  it("translates range filter to $gte/$lte", async () => {
    const db = await initDb();
    await db.search([1, 2, 3, 4], 5, { score: { gte: 0.5, lte: 1.0 } });
    expect(__mocks__.query).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { score: { $gte: 0.5, $lte: 1.0 } },
      }),
    );
  });

  it("translates array filter to $in", async () => {
    const db = await initDb();
    await db.search([1, 2, 3, 4], 5, { tag: ["a", "b"] });
    expect(__mocks__.query).toHaveBeenCalledWith(
      expect.objectContaining({ where: { tag: { $in: ["a", "b"] } } }),
    );
  });

  it("omits wildcard '*' from filter", async () => {
    const db = await initDb();
    await db.search([1, 2, 3, 4], 5, { user_id: "*" });
    const call = __mocks__.query.mock.calls[0][0];
    expect(call.where).toBeUndefined();
  });

  it("translates OR filter", async () => {
    const db = await initDb();
    await db.search([1, 2, 3, 4], 5, {
      OR: [{ tag: "x" }, { tag: "y" }],
    });
    expect(__mocks__.query).toHaveBeenCalledWith(
      expect.objectContaining({
        where: {
          $or: [{ tag: { $eq: "x" } }, { tag: { $eq: "y" } }],
        },
      }),
    );
  });

  it("maps response to VectorStoreResult shape with score from distance", async () => {
    __mocks__.query.mockResolvedValue({
      ids: [["v1", "v2"]],
      distances: [[0, 1]],
      documents: [[null, null]],
      embeddings: [[]],
      metadatas: [[{ text: "hi" }, { text: "bye" }]],
      uris: [[null, null]],
      include: [],
    });
    const db = await initDb();
    const results = await db.search([1, 2, 3, 4]);
    expect(results).toEqual([
      { id: "v1", payload: { text: "hi" }, score: 1.0 },
      { id: "v2", payload: { text: "bye" }, score: 0.5 },
    ]);
  });

  it("returns [] when there are no matches", async () => {
    const db = await initDb();
    const results = await db.search([1, 2, 3, 4]);
    expect(results).toEqual([]);
  });
});

describe("get", () => {
  it("returns VectorStoreResult when record found", async () => {
    __mocks__.get.mockResolvedValue({
      ids: ["vec-1"],
      documents: [null],
      embeddings: [],
      metadatas: [{ text: "foo" }],
      uris: [null],
      include: [],
    });
    const db = await initDb();
    const result = await db.get("vec-1");
    expect(result).toEqual({ id: "vec-1", payload: { text: "foo" } });
  });

  it("returns null when record not found", async () => {
    const db = await initDb();
    const result = await db.get("missing");
    expect(result).toBeNull();
  });
});

describe("update", () => {
  it("updates a single record", async () => {
    const db = await initDb();
    await db.update("vec-1", [1, 2, 3, 4], { text: "updated" });
    expect(__mocks__.update).toHaveBeenCalledWith({
      ids: ["vec-1"],
      embeddings: [[1, 2, 3, 4]],
      metadatas: [{ text: "updated" }],
    });
  });
});

describe("delete", () => {
  it("calls delete with the vectorId", async () => {
    const db = await initDb();
    await db.delete("vec-1");
    expect(__mocks__.delete).toHaveBeenCalledWith({ ids: ["vec-1"] });
  });
});

describe("deleteCol", () => {
  it("calls deleteCollection with the collection name", async () => {
    const db = await initDb();
    await db.deleteCol();
    expect(__mocks__.deleteCollection).toHaveBeenCalledWith({
      name: "test-collection",
    });
  });
});

describe("list", () => {
  it("passes filters and limit through to get", async () => {
    const db = await initDb();
    await db.list({ user_id: "alice" }, 50);
    expect(__mocks__.get).toHaveBeenCalledWith({
      where: { user_id: { $eq: "alice" } },
      limit: 50,
    });
  });

  it("returns the number of matches as the count", async () => {
    __mocks__.get.mockResolvedValue({
      ids: ["a", "b"],
      documents: [null, null],
      embeddings: [],
      metadatas: [{}, {}],
      uris: [null, null],
      include: [],
    });
    const db = await initDb();
    const [results, count] = await db.list();
    expect(results).toHaveLength(2);
    expect(count).toBe(2);
  });
});

describe("getUserId", () => {
  it("returns existing user_id from the migrations collection", async () => {
    __mocks__.get.mockResolvedValue({
      ids: ["mem0-user-id"],
      documents: [null],
      embeddings: [],
      metadatas: [{ user_id: "u-123" }],
      uris: [null],
      include: [],
    });
    const db = await initDb();
    const uid = await db.getUserId();
    expect(uid).toBe("u-123");
  });

  it("generates and adds a new user_id when absent", async () => {
    const db = await initDb();
    const uid = await db.getUserId();
    expect(typeof uid).toBe("string");
    expect(uid.length).toBeGreaterThan(0);
    expect(__mocks__.add).toHaveBeenCalledWith(
      expect.objectContaining({
        ids: ["mem0-user-id"],
        metadatas: [{ user_id: uid }],
      }),
    );
  });
});

describe("setUserId", () => {
  it("adds a new record when none exists", async () => {
    const db = await initDb({ embeddingModelDims: 4 });
    await db.setUserId("u-456");
    expect(__mocks__.add).toHaveBeenCalledWith({
      ids: ["mem0-user-id"],
      embeddings: [[0, 0, 0, 0]],
      metadatas: [{ user_id: "u-456" }],
    });
  });

  it("updates the existing record when one is present", async () => {
    __mocks__.get.mockResolvedValue({
      ids: ["mem0-user-id"],
      documents: [null],
      embeddings: [],
      metadatas: [{ user_id: "u-old" }],
      uris: [null],
      include: [],
    });
    const db = await initDb();
    await db.setUserId("u-456");
    expect(__mocks__.update).toHaveBeenCalledWith({
      ids: ["mem0-user-id"],
      metadatas: [{ user_id: "u-456" }],
    });
  });
});

describe("keywordSearch", () => {
  it("returns null", async () => {
    const db = await initDb();
    const result = await db.keywordSearch();
    expect(result).toBeNull();
  });
});
