// The provider imports `chromadb` lazily (await import) only on first use, so
// the jest.mock factory no longer runs at module-eval time. Create the shared
// mock handles at module top-level (not inside the factory) so `beforeEach` can
// reach them before the lazy import has fired; the factory, which runs on first
// use, just returns references to them.
const add = jest.fn().mockResolvedValue(undefined);
const query = jest
  .fn()
  .mockResolvedValue({ ids: [[]], distances: [[]], metadatas: [[]] });
const get = jest.fn().mockResolvedValue({ ids: [], metadatas: [] });
const update = jest.fn().mockResolvedValue(undefined);
const upsert = jest.fn().mockResolvedValue(undefined);
const deleteFn = jest.fn().mockResolvedValue(undefined);

const collectionHandle = { add, query, get, update, upsert, delete: deleteFn };
const getOrCreateCollection = jest.fn().mockResolvedValue(collectionHandle);
const deleteCollection = jest.fn().mockResolvedValue(undefined);

const clientImpl = () => ({ getOrCreateCollection, deleteCollection });
const ChromaClient = jest.fn().mockImplementation(clientImpl);
const CloudClient = jest.fn().mockImplementation(clientImpl);

const __mocks__ = {
  add,
  query,
  get,
  update,
  upsert,
  deleteFn,
  getOrCreateCollection,
  deleteCollection,
  ChromaClient,
  CloudClient,
};

jest.mock("chromadb", () => ({
  ChromaClient: __mocks__.ChromaClient,
  CloudClient: __mocks__.CloudClient,
}));

import { ChromaDB } from "../vector_stores/chroma";
import { VectorStoreFactory } from "../utils/factory";

// --- Helpers ---

function makeDb(overrides: Record<string, any> = {}): ChromaDB {
  return new ChromaDB({
    collectionName: "test-collection",
    host: "localhost",
    port: 8000,
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

  __mocks__.add.mockResolvedValue(undefined);
  __mocks__.query.mockResolvedValue({
    ids: [[]],
    distances: [[]],
    metadatas: [[]],
  });
  __mocks__.get.mockResolvedValue({ ids: [], metadatas: [] });
  __mocks__.update.mockResolvedValue(undefined);
  __mocks__.upsert.mockResolvedValue(undefined);
  __mocks__.deleteFn.mockResolvedValue(undefined);

  const collectionHandle = {
    add: __mocks__.add,
    query: __mocks__.query,
    get: __mocks__.get,
    update: __mocks__.update,
    upsert: __mocks__.upsert,
    delete: __mocks__.deleteFn,
  };
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
      host: "localhost",
      port: 8000,
    } as any);
    expect(db).toBeInstanceOf(ChromaDB);
    await (db as any).initialize();
  });
});

describe("Constructor", () => {
  // The client is built lazily on first use, so trigger initialize() before
  // asserting how it was constructed.
  it("builds a local ChromaClient with host and port", async () => {
    await initDb({ host: "localhost", port: 8000 });
    expect(__mocks__.ChromaClient).toHaveBeenCalledWith({
      host: "localhost",
      port: 8000,
    });
    expect(__mocks__.CloudClient).not.toHaveBeenCalled();
  });

  it("passes ssl and path through to ChromaClient when provided", async () => {
    await initDb({ host: "example.com", port: 443, ssl: true, path: "/db" });
    expect(__mocks__.ChromaClient).toHaveBeenCalledWith({
      host: "example.com",
      port: 443,
      ssl: true,
      path: "/db",
    });
  });

  it("builds a CloudClient when apiKey and tenant are set", async () => {
    const db = new ChromaDB({
      collectionName: "test-collection",
      apiKey: "key-123",
      tenant: "tenant-abc",
    } as any);
    await db.initialize();
    expect(__mocks__.CloudClient).toHaveBeenCalledWith({
      apiKey: "key-123",
      tenant: "tenant-abc",
      database: "mem0",
    });
    expect(__mocks__.ChromaClient).not.toHaveBeenCalled();
  });

  it("honors an explicit cloud database name", async () => {
    const db = new ChromaDB({
      collectionName: "test-collection",
      apiKey: "key-123",
      tenant: "tenant-abc",
      database: "custom-db",
    } as any);
    await db.initialize();
    expect(__mocks__.CloudClient).toHaveBeenCalledWith(
      expect.objectContaining({ database: "custom-db" }),
    );
  });

  it("accepts a pre-built client via config.client", async () => {
    const fakeClient = {
      getOrCreateCollection: __mocks__.getOrCreateCollection,
      deleteCollection: __mocks__.deleteCollection,
    };
    const db = new ChromaDB({
      collectionName: "test-collection",
      client: fakeClient,
    } as any);
    await db.initialize();
    expect(__mocks__.ChromaClient).not.toHaveBeenCalled();
    expect(__mocks__.CloudClient).not.toHaveBeenCalled();
    expect(__mocks__.getOrCreateCollection).toHaveBeenCalled();
  });
});

describe("initialize", () => {
  it("creates the collection with embeddingFunction null (mem0 supplies embeddings)", async () => {
    await initDb();
    expect(__mocks__.getOrCreateCollection).toHaveBeenCalledWith({
      name: "test-collection",
      embeddingFunction: null,
    });
  });

  it("also creates the migrations collection", async () => {
    await initDb();
    expect(__mocks__.getOrCreateCollection).toHaveBeenCalledWith({
      name: "memory_migrations",
      embeddingFunction: null,
    });
  });
});

describe("insert", () => {
  it("adds records with ids, embeddings, and metadatas", async () => {
    const db = await initDb();
    await db.insert([[1, 2, 3]], ["id-1"], [{ text: "hello" }]);
    expect(__mocks__.add).toHaveBeenCalledWith({
      ids: ["id-1"],
      embeddings: [[1, 2, 3]],
      metadatas: [{ text: "hello" }],
    });
  });
});

describe("search", () => {
  it("queries with embeddings, nResults, and where", async () => {
    const db = await initDb();
    await db.search([1, 2, 3], 10, { user_id: "alice" });
    expect(__mocks__.query).toHaveBeenCalledWith({
      queryEmbeddings: [[1, 2, 3]],
      nResults: 10,
      where: { user_id: { $eq: "alice" } },
    });
  });

  it("maps a nested query response to VectorStoreResult with 1/(1+distance) scores", async () => {
    __mocks__.query.mockResolvedValue({
      ids: [["a", "b"]],
      distances: [[0, 1]],
      metadatas: [[{ k: "v1" }, { k: "v2" }]],
    });
    const db = await initDb();
    const results = await db.search([1, 2, 3]);
    expect(results).toEqual([
      { id: "a", payload: { k: "v1" }, score: 1 },
      { id: "b", payload: { k: "v2" }, score: 0.5 },
    ]);
  });

  it("returns [] when the query yields no matches", async () => {
    __mocks__.query.mockResolvedValue({
      ids: [[]],
      distances: [[]],
      metadatas: [[]],
    });
    const db = await initDb();
    const results = await db.search([1, 2, 3]);
    expect(results).toEqual([]);
  });

  it("passes where undefined when there are no filters", async () => {
    const db = await initDb();
    await db.search([1, 2, 3], 5);
    expect(__mocks__.query).toHaveBeenCalledWith(
      expect.objectContaining({ where: undefined }),
    );
  });
});

describe("get", () => {
  it("fetches by id and returns the first parsed result", async () => {
    __mocks__.get.mockResolvedValue({
      ids: ["vec-1"],
      metadatas: [{ text: "foo" }],
    });
    const db = await initDb();
    const result = await db.get("vec-1");
    expect(__mocks__.get).toHaveBeenCalledWith({ ids: ["vec-1"] });
    expect(result).toEqual({ id: "vec-1", payload: { text: "foo" } });
  });

  it("returns null when the id is not found", async () => {
    __mocks__.get.mockResolvedValue({ ids: [], metadatas: [] });
    const db = await initDb();
    const result = await db.get("missing");
    expect(result).toBeNull();
  });
});

describe("update", () => {
  it("updates a single record with embedding and metadata", async () => {
    const db = await initDb();
    await db.update("vec-1", [1, 2, 3], { text: "updated" });
    expect(__mocks__.update).toHaveBeenCalledWith({
      ids: ["vec-1"],
      embeddings: [[1, 2, 3]],
      metadatas: [{ text: "updated" }],
    });
  });
});

describe("delete", () => {
  it("deletes by id", async () => {
    const db = await initDb();
    await db.delete("vec-1");
    expect(__mocks__.deleteFn).toHaveBeenCalledWith({ ids: ["vec-1"] });
  });
});

describe("deleteCol", () => {
  it("deletes the collection and resets its cached handle", async () => {
    const db = await initDb();
    await db.deleteCol();
    expect(__mocks__.deleteCollection).toHaveBeenCalledWith({
      name: "test-collection",
    });
    // Cached collection promise is cleared, so the next call re-creates it.
    __mocks__.getOrCreateCollection.mockClear();
    await db.search([1, 2, 3]);
    expect(__mocks__.getOrCreateCollection).toHaveBeenCalledWith({
      name: "test-collection",
      embeddingFunction: null,
    });
  });
});

describe("list", () => {
  it("gets with where and limit and returns [results, count]", async () => {
    __mocks__.get.mockResolvedValue({
      ids: ["a", "b"],
      metadatas: [{ k: 1 }, { k: 2 }],
    });
    const db = await initDb();
    const [results, count] = await db.list({ user_id: "alice" }, 50);
    expect(__mocks__.get).toHaveBeenCalledWith({
      where: { user_id: { $eq: "alice" } },
      limit: 50,
    });
    expect(results).toHaveLength(2);
    expect(count).toBe(2);
  });
});

describe("getUserId", () => {
  it("returns an existing user_id from the migrations collection", async () => {
    __mocks__.get.mockResolvedValue({
      ids: ["mig-1"],
      metadatas: [{ user_id: "u-123" }],
    });
    const db = await initDb();
    const uid = await db.getUserId();
    expect(uid).toBe("u-123");
    expect(__mocks__.add).not.toHaveBeenCalled();
  });

  it("generates and stores a new user_id when none exists", async () => {
    __mocks__.get.mockResolvedValue({ ids: [], metadatas: [] });
    const db = await initDb();
    const uid = await db.getUserId();
    expect(typeof uid).toBe("string");
    expect(uid.length).toBeGreaterThan(0);
    expect(__mocks__.add).toHaveBeenCalledWith(
      expect.objectContaining({
        embeddings: [[0]],
        metadatas: [{ user_id: uid }],
      }),
    );
  });
});

describe("setUserId", () => {
  it("upserts the user_id onto the existing migration marker", async () => {
    __mocks__.get.mockResolvedValue({
      ids: ["mig-1"],
      metadatas: [{ user_id: "old" }],
    });
    const db = await initDb();
    await db.setUserId("u-456");
    expect(__mocks__.upsert).toHaveBeenCalledWith({
      ids: ["mig-1"],
      embeddings: [[0]],
      metadatas: [{ user_id: "u-456" }],
    });
  });
});

describe("keywordSearch", () => {
  it("returns null (Chroma has no keyword search)", async () => {
    const db = await initDb();
    const result = await db.keywordSearch();
    expect(result).toBeNull();
  });
});

describe("generateWhereClause", () => {
  it("returns undefined for undefined and empty filters", () => {
    expect(ChromaDB.generateWhereClause(undefined)).toBeUndefined();
    expect(ChromaDB.generateWhereClause({})).toBeUndefined();
  });

  it("converts a single equality filter", () => {
    expect(ChromaDB.generateWhereClause({ user_id: "alice" })).toEqual({
      user_id: { $eq: "alice" },
    });
  });

  it("combines multiple keys with $and", () => {
    expect(
      ChromaDB.generateWhereClause({ user_id: "alice", agent_id: "bot" }),
    ).toEqual({
      $and: [{ user_id: { $eq: "alice" } }, { agent_id: { $eq: "bot" } }],
    });
  });

  it("converts an array value to $in", () => {
    expect(ChromaDB.generateWhereClause({ tags: ["x", "y"] })).toEqual({
      tags: { $in: ["x", "y"] },
    });
  });

  it("skips a wildcard filter", () => {
    expect(ChromaDB.generateWhereClause({ user_id: "*" })).toBeUndefined();
  });

  it("maps comparison operators", () => {
    expect(ChromaDB.generateWhereClause({ age: { gte: 18 } })).toEqual({
      age: { $gte: 18 },
    });
  });

  it("converts an $or block", () => {
    expect(
      ChromaDB.generateWhereClause({ $or: [{ a: "x" }, { b: "y" }] }),
    ).toEqual({ $or: [{ a: { $eq: "x" } }, { b: { $eq: "y" } }] });
  });

  it("collapses a single-branch $or", () => {
    expect(ChromaDB.generateWhereClause({ $or: [{ a: "x" }] })).toEqual({
      a: { $eq: "x" },
    });
  });

  it("negates a single-field $not condition", () => {
    expect(ChromaDB.generateWhereClause({ $not: [{ a: "x" }] })).toEqual({
      a: { $ne: "x" },
    });
  });

  it("applies De Morgan to a multi-field $not condition", () => {
    // NOT(a=x AND b=y) is (a!=x) OR (b!=y)
    expect(
      ChromaDB.generateWhereClause({ $not: [{ a: "x", b: "y" }] }),
    ).toEqual({ $or: [{ a: { $ne: "x" } }, { b: { $ne: "y" } }] });
  });

  it("negates a $not comparison operator", () => {
    expect(
      ChromaDB.generateWhereClause({ $not: [{ age: { gt: 18 } }] }),
    ).toEqual({ age: { $lte: 18 } });
  });
});
