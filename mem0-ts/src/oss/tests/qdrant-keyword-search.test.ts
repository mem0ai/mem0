/// <reference types="jest" />
/**
 * Tests for Qdrant native BM25 keyword search (server-side `Qdrant/bm25`
 * inference). Fully mocked — no real Qdrant server is required.
 *
 * Covers both the happy path and the failure modes that matter for an opt-in,
 * capability-gated feature:
 *  - fresh collections get the `bm25` sparse slot (modifier idf); migrations don't,
 *  - insert/update attach the server-side BM25 inference vector,
 *  - keywordSearch queries the `bm25` slot and maps results to the common shape,
 *  - collection-init variations (slot present/absent, wrong size, 401/403/409,
 *    transient verify failure, fatal error),
 *  - malformed/hostile query responses and filter construction,
 * all proving the adapter degrades to `null` (semantic-only) instead of crashing.
 */

jest.setTimeout(15000);

type MockClient = Record<string, jest.Mock>;

function buildMockClient(
  overrides: Partial<MockClient> = {},
  collectionInfo: any = { config: { params: { vectors: { size: 768 } } } },
): MockClient {
  return {
    createCollection: jest.fn().mockResolvedValue(undefined),
    createPayloadIndex: jest.fn().mockResolvedValue(undefined),
    getCollection: jest.fn().mockResolvedValue(collectionInfo),
    scroll: jest.fn().mockResolvedValue({ points: [] }),
    upsert: jest.fn().mockResolvedValue(undefined),
    retrieve: jest.fn().mockResolvedValue([]),
    search: jest.fn().mockResolvedValue([]),
    query: jest.fn().mockResolvedValue({ points: [] }),
    delete: jest.fn().mockResolvedValue(undefined),
    deleteCollection: jest.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

jest.mock("@qdrant/js-client-rest", () => ({
  QdrantClient: jest.fn().mockImplementation(() => buildMockClient()),
}));

import { Qdrant } from "../src/vector_stores/qdrant";

const BASE_CONFIG = {
  collectionName: "test_memories",
  embeddingModelDims: 768,
  dimension: 768,
};

// Existing collection that already carries a bm25 slot.
const INFO_WITH_SLOT = {
  config: {
    params: { vectors: { size: 768 }, sparse_vectors: { bm25: {} } },
  },
};
// Existing collection without a bm25 slot (legacy / pre-hybrid-search).
const INFO_NO_SLOT = {
  config: { params: { vectors: { size: 768 } } },
};

let warnSpy: jest.SpyInstance;
let errSpy: jest.SpyInstance;

beforeEach(() => {
  jest.clearAllMocks();
  warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
  errSpy = jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  warnSpy.mockRestore();
  errSpy.mockRestore();
});

function makeStore(client: MockClient): Qdrant {
  return new Qdrant({ client: client as any, ...BASE_CONFIG });
}

describe("Qdrant BM25 keyword search — collection setup", () => {
  it("creates the main collection with the bm25 sparse slot (modifier idf)", async () => {
    const client = buildMockClient();
    const store = makeStore(client);
    await store.initialize();

    const createCall = client.createCollection.mock.calls.find(
      (c) => c[0] === "test_memories",
    );
    expect(createCall).toBeDefined();
    expect(createCall![1].sparse_vectors).toEqual({
      bm25: { modifier: "idf" },
    });
  });

  it("does NOT add the bm25 slot to the memory_migrations collection", async () => {
    const client = buildMockClient();
    const store = makeStore(client);
    await store.initialize();

    const migrationsCall = client.createCollection.mock.calls.find(
      (c) => c[0] === "memory_migrations",
    );
    expect(migrationsCall).toBeDefined();
    expect(migrationsCall![1].sparse_vectors).toBeUndefined();
  });

  it("409 with an existing bm25 slot → enables keyword search, no warning", async () => {
    const client = buildMockClient(
      { createCollection: jest.fn().mockRejectedValue({ status: 409 }) },
      INFO_WITH_SLOT,
    );
    const store = makeStore(client);
    await store.initialize();

    expect(await store.keywordSearch("anything")).not.toBeNull();
    expect(client.query).toHaveBeenCalled();
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it("409 without a bm25 slot → disabled + warns once", async () => {
    const client = buildMockClient(
      { createCollection: jest.fn().mockRejectedValue({ status: 409 }) },
      INFO_NO_SLOT,
    );
    const store = makeStore(client);
    await store.initialize();

    expect(await store.keywordSearch("anything")).toBeNull();
    expect(client.query).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledTimes(1);
  });

  it("401 (auth-restricted existing collection) with slot → enabled", async () => {
    const client = buildMockClient(
      { createCollection: jest.fn().mockRejectedValue({ status: 401 }) },
      INFO_WITH_SLOT,
    );
    const store = makeStore(client);
    await store.initialize();
    expect(await store.keywordSearch("x")).not.toBeNull();
  });

  it("403 with no slot → disabled (graceful)", async () => {
    const client = buildMockClient(
      { createCollection: jest.fn().mockRejectedValue({ status: 403 }) },
      INFO_NO_SLOT,
    );
    const store = makeStore(client);
    await store.initialize();
    expect(await store.keywordSearch("x")).toBeNull();
  });

  it("existing collection with WRONG vector size → init rejects (size guard intact)", async () => {
    const client = buildMockClient(
      { createCollection: jest.fn().mockRejectedValue({ status: 409 }) },
      { config: { params: { vectors: { size: 1536 } } } }, // mismatch vs 768
    );
    const store = makeStore(client);
    await expect(store.initialize()).rejects.toThrow(/wrong vector size/i);
  });

  it("transient getCollection failure during verify → does NOT crash init, stays disabled", async () => {
    const client = buildMockClient({
      createCollection: jest.fn().mockRejectedValue({ status: 409 }),
      getCollection: jest
        .fn()
        .mockRejectedValue({ status: 500, message: "committing" }),
    });
    const store = makeStore(client);
    await expect(store.initialize()).resolves.toBeUndefined();
    expect(await store.keywordSearch("x")).toBeNull();
  });

  it("fatal createCollection error (500, not 401/403/409) → init rejects", async () => {
    const client = buildMockClient({
      createCollection: jest.fn().mockRejectedValue({ status: 500 }),
    });
    const store = makeStore(client);
    await expect(store.initialize()).rejects.toBeDefined();
  });
});

describe("Qdrant BM25 keyword search — insert / update", () => {
  async function freshStore(): Promise<{ store: Qdrant; client: MockClient }> {
    const client = buildMockClient();
    const store = makeStore(client);
    await store.initialize();
    return { store, client };
  }

  it("attaches a server-side BM25 inference vector on insert", async () => {
    const { store, client } = await freshStore();
    await store.insert(
      [[0.1, 0.2, 0.3]],
      ["mem-1"],
      [
        {
          data: "Alice reported a duplicate AWS invoice",
          textLemmatized: "alice report duplicate aws invoice",
        },
      ],
    );

    const point = client.upsert.mock.calls.at(-1)![1].points[0];
    expect(point.id).toBe("mem-1");
    expect(point.vector[""]).toEqual([0.1, 0.2, 0.3]);
    expect(point.vector.bm25).toEqual({
      text: "alice report duplicate aws invoice",
      model: "Qdrant/bm25",
    });
  });

  it("falls back to payload.data when textLemmatized is absent", async () => {
    const { store, client } = await freshStore();
    await store.insert([[0.1]], ["mem-2"], [{ data: "plain text" }]);

    const point = client.upsert.mock.calls.at(-1)![1].points[0];
    expect(point.vector.bm25).toEqual({
      text: "plain text",
      model: "Qdrant/bm25",
    });
  });

  it("empty textLemmatized falls through to data", async () => {
    const { store, client } = await freshStore();
    await store.insert(
      [[0.1]],
      ["m"],
      [{ textLemmatized: "", data: "fallback" }],
    );
    const point = client.upsert.mock.calls.at(-1)![1].points[0];
    expect(point.vector.bm25).toEqual({
      text: "fallback",
      model: "Qdrant/bm25",
    });
  });

  it("omits the bm25 vector when the point has no text (dense still present)", async () => {
    const { store, client } = await freshStore();
    await store.insert([[0.1, 0.2]], ["m"], [{ textLemmatized: "", data: "" }]);
    const point = client.upsert.mock.calls.at(-1)![1].points[0];
    expect(point.vector[""]).toEqual([0.1, 0.2]);
    expect(point.vector.bm25).toBeUndefined();
  });

  it("preserves the given id on insert", async () => {
    const { store, client } = await freshStore();
    await store.insert([[0.1]], ["123"], [{ data: "x" }]);
    const point = client.upsert.mock.calls.at(-1)![1].points[0];
    expect(point.id).toBe("123");
  });

  it("batch insert attaches bm25 to every text-bearing point", async () => {
    const { store, client } = await freshStore();
    await store.insert(
      [[0.1], [0.2], [0.3]],
      ["a", "b", "c"],
      [{ data: "one" }, { data: "" }, { textLemmatized: "three" }],
    );
    const points = client.upsert.mock.calls.at(-1)![1].points;
    expect(points[0].vector.bm25.text).toBe("one");
    expect(points[1].vector.bm25).toBeUndefined();
    expect(points[2].vector.bm25.text).toBe("three");
  });

  it("re-encodes the bm25 vector on update", async () => {
    const { store, client } = await freshStore();
    await store.update("mem-1", [0.4, 0.5], {
      data: "updated",
      textLemmatized: "updat",
    });
    const point = client.upsert.mock.calls.at(-1)![1].points[0];
    expect(point.vector[""]).toEqual([0.4, 0.5]);
    expect(point.vector.bm25).toEqual({ text: "updat", model: "Qdrant/bm25" });
  });

  it("update with no text → named dense only (bm25 not re-attached)", async () => {
    const { store, client } = await freshStore();
    await store.update("m", [0.9], { user_id: "u" });
    const point = client.upsert.mock.calls.at(-1)![1].points[0];
    expect(point.vector[""]).toEqual([0.9]);
    expect(point.vector.bm25).toBeUndefined();
  });

  it("inserts a plain dense vector (no named/sparse) on legacy collections", async () => {
    const client = buildMockClient(
      { createCollection: jest.fn().mockRejectedValue({ status: 409 }) },
      INFO_NO_SLOT,
    );
    const store = makeStore(client);
    await store.initialize();

    await store.insert(
      [[0.1, 0.2]],
      ["mem-1"],
      [{ data: "hello", textLemmatized: "hello" }],
    );

    const point = client.upsert.mock.calls.at(-1)![1].points[0];
    expect(point.vector).toEqual([0.1, 0.2]);
  });
});

describe("Qdrant BM25 keyword search — querying & result mapping", () => {
  it("queries the bm25 slot and maps results to {id, payload, score}", async () => {
    const client = buildMockClient({
      query: jest.fn().mockResolvedValue({
        points: [
          { id: "mem-1", score: 4.2, payload: { data: "AWS invoice" } },
          { id: "mem-2", score: 1.1, payload: { data: "other" } },
        ],
      }),
    });
    const store = makeStore(client);
    await store.initialize();

    const results = await store.keywordSearch("aws invoice", 5, {
      user_id: "u1",
    });

    expect(client.query).toHaveBeenCalledWith(
      "test_memories",
      expect.objectContaining({
        query: { text: "aws invoice", model: "Qdrant/bm25" },
        using: "bm25",
        limit: 5,
        with_payload: true,
      }),
    );
    expect(results).toEqual([
      { id: "mem-1", payload: { data: "AWS invoice" }, score: 4.2 },
      { id: "mem-2", payload: { data: "other" }, score: 1.1 },
    ]);
  });

  async function storeWith(queryImpl: jest.Mock): Promise<Qdrant> {
    const client = buildMockClient({ query: queryImpl });
    const store = makeStore(client);
    await store.initialize();
    return store;
  }

  it("query rejects → null (no throw)", async () => {
    const store = await storeWith(
      jest.fn().mockRejectedValue(new Error("boom")),
    );
    expect(await store.keywordSearch("x")).toBeNull();
    expect(errSpy).toHaveBeenCalled();
  });

  it("response missing the `points` array → null (no throw)", async () => {
    const store = await storeWith(jest.fn().mockResolvedValue({}));
    expect(await store.keywordSearch("x")).toBeNull();
    expect(errSpy).toHaveBeenCalled();
  });

  it("response is null → null (no throw)", async () => {
    const store = await storeWith(jest.fn().mockResolvedValue(null));
    expect(await store.keywordSearch("x")).toBeNull();
  });

  it("point with numeric id → stringified", async () => {
    const store = await storeWith(
      jest.fn().mockResolvedValue({
        points: [{ id: 42, score: 1.0, payload: { data: "d" } }],
      }),
    );
    const res = await store.keywordSearch("x");
    expect(res![0].id).toBe("42");
  });

  it("point with missing score → score undefined (pipeline coerces to 0)", async () => {
    const store = await storeWith(
      jest.fn().mockResolvedValue({ points: [{ id: "a", payload: {} }] }),
    );
    const res = await store.keywordSearch("x");
    expect(res![0].score).toBeUndefined();
  });

  it("point with missing payload → {}", async () => {
    const store = await storeWith(
      jest.fn().mockResolvedValue({ points: [{ id: "a", score: 2 }] }),
    );
    const res = await store.keywordSearch("x");
    expect(res![0].payload).toEqual({});
  });

  it("empty query string is forwarded and yields [] (graceful)", async () => {
    const queryImpl = jest.fn().mockResolvedValue({ points: [] });
    const store = await storeWith(queryImpl);
    const res = await store.keywordSearch("");
    expect(res).toEqual([]);
    expect(queryImpl.mock.calls[0][1].query).toEqual({
      text: "",
      model: "Qdrant/bm25",
    });
  });
});

describe("Qdrant BM25 keyword search — query construction & filters", () => {
  async function freshStore(): Promise<{ store: Qdrant; client: MockClient }> {
    const client = buildMockClient();
    const store = makeStore(client);
    await store.initialize();
    return { store, client };
  }

  it("defaults topK to 5 when omitted", async () => {
    const { store, client } = await freshStore();
    await store.keywordSearch("x");
    expect(client.query.mock.calls[0][1].limit).toBe(5);
  });

  it("passes a simple equality filter through createFilter", async () => {
    const { store, client } = await freshStore();
    await store.keywordSearch("x", 3, { user_id: "u1" });
    const arg = client.query.mock.calls[0][1];
    expect(arg.limit).toBe(3);
    expect(arg.using).toBe("bm25");
    expect(arg.filter).toEqual({
      must: [{ key: "user_id", match: { value: "u1" } }],
    });
  });

  it("builds an OR (should) clause for logical filters", async () => {
    const { store, client } = await freshStore();
    await store.keywordSearch("x", 5, {
      $or: [{ user_id: "u1" }, { agent_id: "a1" }],
    });
    const filter = client.query.mock.calls[0][1].filter;
    expect(filter.should).toHaveLength(2);
  });

  it("empty filter object → filter is undefined", async () => {
    const { store, client } = await freshStore();
    await store.keywordSearch("x", 5, {});
    expect(client.query.mock.calls[0][1].filter).toBeUndefined();
  });
});
