// jest.mock is hoisted before variable declarations, so we cannot close over
// variables declared with let/const. All shared mock functions are attached to
// the module-level `__mocks__` object that is populated inside the factory so
// that the hoisted mock can reach them via a stable reference.

const __mocks__: {
  upsert: jest.Mock;
  query: jest.Mock;
  fetch: jest.Mock;
  deleteOne: jest.Mock;
  namespace: jest.Mock;
  describeIndexStats: jest.Mock;
  index: jest.Mock;
  listIndexes: jest.Mock;
  createIndex: jest.Mock;
  deleteIndex: jest.Mock;
  Pinecone: jest.Mock;
} = {} as any;

jest.mock("@pinecone-database/pinecone", () => {
  // These are created fresh inside the factory so hoisting is safe.
  const upsert = jest.fn().mockResolvedValue(undefined);
  const query = jest.fn().mockResolvedValue({ matches: [] });
  const fetch = jest.fn().mockResolvedValue({ records: {} });
  const deleteOne = jest.fn().mockResolvedValue(undefined);

  const nsHandle = { upsert, query, fetch, deleteOne };
  const namespace = jest.fn().mockReturnValue(nsHandle);

  const describeIndexStats = jest
    .fn()
    .mockResolvedValue({ totalRecordCount: 0, namespaces: {} });

  const indexHandle = {
    namespace,
    describeIndexStats,
    // expose ops directly for the no-namespace path
    upsert,
    query,
    fetch,
    deleteOne,
  };
  const index = jest.fn().mockReturnValue(indexHandle);

  const listIndexes = jest.fn().mockResolvedValue({ indexes: [] });
  const createIndex = jest.fn().mockResolvedValue(undefined);
  const deleteIndex = jest.fn().mockResolvedValue(undefined);

  const Pinecone = jest.fn().mockImplementation(() => ({
    listIndexes,
    createIndex,
    deleteIndex,
    index,
  }));

  // Populate the shared reference so tests can reach the mocks.
  Object.assign(__mocks__, {
    upsert,
    query,
    fetch,
    deleteOne,
    namespace,
    describeIndexStats,
    index,
    listIndexes,
    createIndex,
    deleteIndex,
    Pinecone,
  });

  return { Pinecone };
});

import { PineconeDB } from "../vector_stores/pinecone";
import { VectorStoreFactory } from "../utils/factory";

// --- Helpers ---

function makeDb(overrides: Record<string, any> = {}): PineconeDB {
  return new PineconeDB({
    collectionName: "test-index",
    embeddingModelDims: 4,
    apiKey: "test-api-key",
    ...overrides,
  } as any);
}

async function initDb(
  overrides: Record<string, any> = {},
): Promise<PineconeDB> {
  const db = makeDb(overrides);
  await db.initialize();
  return db;
}

// --- Reset mocks between tests ---

beforeEach(() => {
  jest.clearAllMocks();

  __mocks__.listIndexes.mockResolvedValue({ indexes: [] });
  __mocks__.createIndex.mockResolvedValue(undefined);
  __mocks__.deleteIndex.mockResolvedValue(undefined);
  __mocks__.upsert.mockResolvedValue(undefined);
  __mocks__.query.mockResolvedValue({ matches: [] });
  __mocks__.fetch.mockResolvedValue({ records: {} });
  __mocks__.deleteOne.mockResolvedValue(undefined);
  __mocks__.describeIndexStats.mockResolvedValue({
    totalRecordCount: 0,
    namespaces: {},
  });

  const nsHandle = {
    upsert: __mocks__.upsert,
    query: __mocks__.query,
    fetch: __mocks__.fetch,
    deleteOne: __mocks__.deleteOne,
  };
  __mocks__.namespace.mockReturnValue(nsHandle);
  __mocks__.index.mockReturnValue({
    namespace: __mocks__.namespace,
    describeIndexStats: __mocks__.describeIndexStats,
    upsert: __mocks__.upsert,
    query: __mocks__.query,
    fetch: __mocks__.fetch,
    deleteOne: __mocks__.deleteOne,
  });
  __mocks__.Pinecone.mockImplementation(() => ({
    listIndexes: __mocks__.listIndexes,
    createIndex: __mocks__.createIndex,
    deleteIndex: __mocks__.deleteIndex,
    index: __mocks__.index,
  }));
});

// --- Test suites ---

describe("VectorStoreFactory", () => {
  it("returns a PineconeDB instance for provider 'pinecone'", async () => {
    const db = VectorStoreFactory.create("pinecone", {
      collectionName: "x",
      embeddingModelDims: 4,
      apiKey: "k",
    } as any);
    expect(db).toBeInstanceOf(PineconeDB);
    await (db as any).initialize();
  });
});

describe("Constructor", () => {
  it("uses apiKey from config", async () => {
    await initDb({ apiKey: "from-config" });
    expect(__mocks__.Pinecone).toHaveBeenCalledWith({ apiKey: "from-config" });
  });

  it("falls back to PINECONE_API_KEY env var", async () => {
    process.env.PINECONE_API_KEY = "env-key";
    try {
      const db = new PineconeDB({
        collectionName: "test-index",
        embeddingModelDims: 4,
      } as any);
      await db.initialize();
      expect(__mocks__.Pinecone).toHaveBeenCalledWith({ apiKey: "env-key" });
    } finally {
      delete process.env.PINECONE_API_KEY;
    }
  });

  it("throws when no API key is provided", () => {
    delete process.env.PINECONE_API_KEY;
    expect(
      () =>
        new PineconeDB({
          collectionName: "test-index",
          embeddingModelDims: 4,
        } as any),
    ).toThrow("Pinecone API key required");
  });

  it("accepts a pre-built client via config.client", async () => {
    const fakeClient = {
      listIndexes: __mocks__.listIndexes,
      createIndex: __mocks__.createIndex,
      deleteIndex: __mocks__.deleteIndex,
      index: __mocks__.index,
    };
    const db = new PineconeDB({
      collectionName: "test-index",
      embeddingModelDims: 4,
      client: fakeClient,
    } as any);
    await db.initialize();
    expect(__mocks__.Pinecone).not.toHaveBeenCalled();
    expect(__mocks__.listIndexes).toHaveBeenCalled();
  });
});

describe("initialize", () => {
  it("creates index with serverless default spec when index does not exist", async () => {
    await initDb();
    expect(__mocks__.createIndex).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "test-index",
        dimension: 4,
        metric: "cosine",
        spec: { serverless: { cloud: "aws", region: "us-east-1" } },
        waitUntilReady: true,
      }),
    );
  });

  it("creates index with pod spec when podConfig provided", async () => {
    await initDb({
      podConfig: { environment: "us-east1-gcp", podType: "p1.x2", pods: 2 },
    });
    expect(__mocks__.createIndex).toHaveBeenCalledWith(
      expect.objectContaining({
        spec: {
          pod: {
            environment: "us-east1-gcp",
            podType: "p1.x2",
            pods: 2,
            replicas: 1,
            shards: 1,
          },
        },
      }),
    );
  });

  it("skips createIndex when index already exists", async () => {
    __mocks__.listIndexes.mockResolvedValue({
      indexes: [{ name: "test-index" }],
    });
    await initDb();
    expect(__mocks__.createIndex).not.toHaveBeenCalled();
  });

  it("_initPromise is shared across concurrent calls (idempotent)", async () => {
    // makeDb() fires initialize() in the constructor; calling it again before
    // it resolves must reuse the same in-flight promise so createIndex runs only once.
    const db = makeDb();
    await Promise.all([db.initialize(), db.initialize(), db.initialize()]);
    expect(__mocks__.createIndex).toHaveBeenCalledTimes(1);
  });
});

describe("insert", () => {
  it("upserts records with correct shape", async () => {
    const db = await initDb();
    await db.insert([[1, 2, 3, 4]], ["id-1"], [{ text: "hello" }]);
    expect(__mocks__.upsert).toHaveBeenCalledWith({
      records: [
        { id: "id-1", values: [1, 2, 3, 4], metadata: { text: "hello" } },
      ],
    });
  });

  it("splits 150 records into two batches with batchSize=100", async () => {
    const db = await initDb({ batchSize: 100 });
    const vectors = Array.from({ length: 150 }, () => [0, 0, 0, 0]);
    const ids = Array.from({ length: 150 }, (_, i) => `id-${i}`);
    const payloads = Array.from({ length: 150 }, () => ({}));
    await db.insert(vectors, ids, payloads);
    expect(__mocks__.upsert).toHaveBeenCalledTimes(2);
    expect(__mocks__.upsert.mock.calls[0][0].records).toHaveLength(100);
    expect(__mocks__.upsert.mock.calls[1][0].records).toHaveLength(50);
  });
});

describe("search", () => {
  it("calls query with correct args", async () => {
    const db = await initDb();
    await db.search([1, 2, 3, 4], 10);
    expect(__mocks__.query).toHaveBeenCalledWith(
      expect.objectContaining({
        vector: [1, 2, 3, 4],
        topK: 10,
        includeMetadata: true,
        includeValues: false,
      }),
    );
  });

  it("translates equality filter to Pinecone $eq", async () => {
    const db = await initDb();
    await db.search([1, 2, 3, 4], 5, { user_id: "alice" });
    expect(__mocks__.query).toHaveBeenCalledWith(
      expect.objectContaining({
        filter: { user_id: { $eq: "alice" } },
      }),
    );
  });

  it("translates range filter to $gte/$lte", async () => {
    const db = await initDb();
    await db.search([1, 2, 3, 4], 5, { score: { gte: 0.5, lte: 1.0 } });
    expect(__mocks__.query).toHaveBeenCalledWith(
      expect.objectContaining({
        filter: { score: { $gte: 0.5, $lte: 1.0 } },
      }),
    );
  });

  it("translates array filter to $in", async () => {
    const db = await initDb();
    await db.search([1, 2, 3, 4], 5, { tag: ["a", "b"] });
    expect(__mocks__.query).toHaveBeenCalledWith(
      expect.objectContaining({ filter: { tag: { $in: ["a", "b"] } } }),
    );
  });

  it("omits wildcard '*' from filter", async () => {
    const db = await initDb();
    await db.search([1, 2, 3, 4], 5, { user_id: "*" });
    const call = __mocks__.query.mock.calls[0][0];
    expect(call.filter).toBeUndefined();
  });

  it("translates OR filter", async () => {
    const db = await initDb();
    await db.search([1, 2, 3, 4], 5, {
      OR: [{ tag: "x" }, { tag: "y" }],
    });
    expect(__mocks__.query).toHaveBeenCalledWith(
      expect.objectContaining({
        filter: {
          $or: [{ tag: { $eq: "x" } }, { tag: { $eq: "y" } }],
        },
      }),
    );
  });

  it("passes no filter when filters is empty", async () => {
    const db = await initDb();
    await db.search([1, 2, 3, 4], 5, {});
    const call = __mocks__.query.mock.calls[0][0];
    expect(call.filter).toBeUndefined();
  });

  it("warns and skips NOT operator (unsupported by Pinecone)", async () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const db = await initDb();
    await db.search([1, 2, 3, 4], 5, { NOT: [{ tag: "x" }] });
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining("NOT"));
    warnSpy.mockRestore();
  });

  it("warns and skips contains operator", async () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const db = await initDb();
    await db.search([1, 2, 3, 4], 5, { tag: { contains: "foo" } });
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining("contains"));
    warnSpy.mockRestore();
  });

  it("throws on unsupported filter operator", async () => {
    const db = await initDb();
    await expect(
      db.search([1, 2, 3, 4], 5, { tag: { regex: "^foo" } } as any),
    ).rejects.toThrow();
  });

  it("maps response matches to VectorStoreResult shape", async () => {
    __mocks__.query.mockResolvedValue({
      matches: [
        { id: "v1", metadata: { text: "hi" }, score: 0.9 },
        { id: "v2", metadata: { text: "bye" }, score: 0.7 },
      ],
    });
    const db = await initDb();
    const results = await db.search([1, 2, 3, 4]);
    expect(results).toEqual([
      { id: "v1", payload: { text: "hi" }, score: 0.9 },
      { id: "v2", payload: { text: "bye" }, score: 0.7 },
    ]);
  });

  it("returns [] when matches is empty", async () => {
    __mocks__.query.mockResolvedValue({ matches: [] });
    const db = await initDb();
    const results = await db.search([1, 2, 3, 4]);
    expect(results).toEqual([]);
  });
});

describe("get", () => {
  it("returns VectorStoreResult when record found", async () => {
    __mocks__.fetch.mockResolvedValue({
      records: {
        "vec-1": { id: "vec-1", metadata: { text: "foo" } },
      },
    });
    const db = await initDb();
    const result = await db.get("vec-1");
    expect(result).toEqual({ id: "vec-1", payload: { text: "foo" } });
  });

  it("returns null when record not found", async () => {
    __mocks__.fetch.mockResolvedValue({ records: {} });
    const db = await initDb();
    const result = await db.get("missing");
    expect(result).toBeNull();
  });
});

describe("update", () => {
  it("upserts a single record", async () => {
    const db = await initDb();
    await db.update("vec-1", [1, 2, 3, 4], { text: "updated" });
    expect(__mocks__.upsert).toHaveBeenCalledWith({
      records: [
        { id: "vec-1", values: [1, 2, 3, 4], metadata: { text: "updated" } },
      ],
    });
  });
});

describe("delete", () => {
  it("calls deleteOne with the vectorId", async () => {
    const db = await initDb();
    await db.delete("vec-1");
    expect(__mocks__.deleteOne).toHaveBeenCalledWith({ id: "vec-1" });
  });
});

describe("deleteCol", () => {
  it("calls deleteIndex and resets internal state so re-init creates fresh index", async () => {
    const db = await initDb();
    await db.deleteCol();
    expect(__mocks__.deleteIndex).toHaveBeenCalledWith("test-index");
    // After deleteCol, _index and _initPromise reset; next initialize triggers createIndex again.
    __mocks__.listIndexes.mockResolvedValue({ indexes: [] });
    await db.initialize();
    expect(__mocks__.createIndex).toHaveBeenCalledTimes(2);
  });
});

describe("list", () => {
  it("passes zero vector to query", async () => {
    const db = await initDb({ embeddingModelDims: 4 });
    await db.list();
    expect(__mocks__.query).toHaveBeenCalledWith(
      expect.objectContaining({ vector: [0, 0, 0, 0] }),
    );
  });

  it("returns the number of matches as the count", async () => {
    __mocks__.query.mockResolvedValue({
      matches: [
        { id: "a", metadata: {}, score: 0 },
        { id: "b", metadata: {}, score: 0 },
      ],
    });
    const db = await initDb();
    const [results, count] = await db.list();
    expect(results).toHaveLength(2);
    expect(count).toBe(2);
  });

  it("does not make an extra describeIndexStats round-trip", async () => {
    __mocks__.query.mockResolvedValue({ matches: [] });
    const db = await initDb();
    await db.list();
    expect(__mocks__.describeIndexStats).not.toHaveBeenCalled();
  });
});

describe("getUserId", () => {
  it("returns existing user_id from migrations namespace", async () => {
    __mocks__.fetch.mockResolvedValue({
      records: {
        "mem0-user-id": {
          id: "mem0-user-id",
          metadata: { user_id: "u-123" },
        },
      },
    });
    const db = await initDb();
    const uid = await db.getUserId();
    expect(uid).toBe("u-123");
    expect(__mocks__.namespace).toHaveBeenCalledWith("__mem0_migrations__");
  });

  it("generates and upserts a new user_id when absent", async () => {
    __mocks__.fetch.mockResolvedValue({ records: {} });
    const db = await initDb();
    const uid = await db.getUserId();
    expect(typeof uid).toBe("string");
    expect(uid.length).toBeGreaterThan(0);
    expect(__mocks__.upsert).toHaveBeenCalledWith(
      expect.objectContaining({
        records: expect.arrayContaining([
          expect.objectContaining({
            id: "mem0-user-id",
            metadata: { user_id: uid },
          }),
        ]),
      }),
    );
    expect(__mocks__.namespace).toHaveBeenCalledWith("__mem0_migrations__");
  });
});

describe("setUserId", () => {
  it("upserts with correct id, zero vector, and metadata", async () => {
    const db = await initDb({ embeddingModelDims: 4 });
    await db.setUserId("u-456");
    expect(__mocks__.upsert).toHaveBeenCalledWith({
      records: [
        {
          id: "mem0-user-id",
          values: [0, 0, 0, 0],
          metadata: { user_id: "u-456" },
        },
      ],
    });
    expect(__mocks__.namespace).toHaveBeenCalledWith("__mem0_migrations__");
  });
});

describe("keywordSearch", () => {
  it("returns null", async () => {
    const db = await initDb();
    const result = await db.keywordSearch("hello", 5);
    expect(result).toBeNull();
  });
});
