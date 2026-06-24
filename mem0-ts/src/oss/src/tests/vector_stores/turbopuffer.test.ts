import { TurbopufferDB } from "../../vector_stores/turbopuffer";

// Mock the @turbopuffer/turbopuffer package
const mockWrite = jest.fn().mockResolvedValue(undefined);
const mockQuery = jest.fn();
const mockDeleteAll = jest.fn().mockResolvedValue(undefined);

const mockMigrationsNs = {
  write: jest.fn().mockResolvedValue(undefined),
  query: jest.fn(),
  deleteAll: jest.fn().mockResolvedValue(undefined),
};

const mockNs = {
  write: mockWrite,
  query: mockQuery,
  deleteAll: mockDeleteAll,
};

const mockNamespace = jest.fn((name: string) => {
  if (name.endsWith("_migrations")) return mockMigrationsNs;
  return mockNs;
});

jest.mock("@turbopuffer/turbopuffer", () => ({
  __esModule: true,
  default: jest.fn().mockImplementation(() => ({
    namespace: mockNamespace,
  })),
}));

function makeStore(overrides: Record<string, any> = {}): TurbopufferDB {
  return new TurbopufferDB({
    apiKey: "test-key",
    collectionName: "test-ns",
    embeddingModelDims: 3,
    ...overrides,
  } as any);
}

beforeEach(() => {
  jest.clearAllMocks();
  mockWrite.mockResolvedValue(undefined);
  mockQuery.mockResolvedValue({ rows: [] });
  mockDeleteAll.mockResolvedValue(undefined);
  mockMigrationsNs.write.mockResolvedValue(undefined);
  mockMigrationsNs.query.mockResolvedValue({ rows: [] });
  mockMigrationsNs.deleteAll.mockResolvedValue(undefined);
});

describe("TurbopufferDB constructor", () => {
  it("throws when no API key is provided", () => {
    const orig = process.env.TURBOPUFFER_API_KEY;
    delete process.env.TURBOPUFFER_API_KEY;
    expect(
      () =>
        new TurbopufferDB({
          collectionName: "c",
          embeddingModelDims: 3,
        } as any),
    ).toThrow(/API key/);
    process.env.TURBOPUFFER_API_KEY = orig;
  });

  it("reads API key from environment variable", () => {
    process.env.TURBOPUFFER_API_KEY = "env-key";
    expect(
      () =>
        new TurbopufferDB({
          collectionName: "c",
          embeddingModelDims: 3,
        } as any),
    ).not.toThrow();
    delete process.env.TURBOPUFFER_API_KEY;
  });
});

describe("TurbopufferDB initialize", () => {
  it("resolves without calling write", async () => {
    const store = makeStore();
    await expect(store.initialize()).resolves.toBeUndefined();
    expect(mockWrite).not.toHaveBeenCalled();
  });
});

describe("TurbopufferDB keywordSearch", () => {
  it("returns null", async () => {
    const store = makeStore();
    expect(await store.keywordSearch()).toBeNull();
  });
});

describe("TurbopufferDB insert", () => {
  it("calls write with upsert_rows containing id and vector", async () => {
    const store = makeStore();
    await store.insert([[0.1, 0.2, 0.3]], ["id-1"], [{ data: "hello" }]);
    expect(mockWrite).toHaveBeenCalledTimes(1);
    expect(mockWrite).toHaveBeenCalledWith({
      upsert_rows: [{ data: "hello", id: "id-1", vector: [0.1, 0.2, 0.3] }],
      distance_metric: "cosine_distance",
    });
  });

  it("batches into multiple write calls when batchSize is exceeded", async () => {
    const store = makeStore({ batchSize: 1 });
    await store.insert(
      [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
      ],
      ["id-1", "id-2"],
      [{ a: 1 }, { b: 2 }],
    );
    expect(mockWrite).toHaveBeenCalledTimes(2);
    expect(mockWrite).toHaveBeenNthCalledWith(1, {
      upsert_rows: [{ a: 1, id: "id-1", vector: [0.1, 0.2, 0.3] }],
      distance_metric: "cosine_distance",
    });
    expect(mockWrite).toHaveBeenNthCalledWith(2, {
      upsert_rows: [{ b: 2, id: "id-2", vector: [0.4, 0.5, 0.6] }],
      distance_metric: "cosine_distance",
    });
  });

  it("explicit id in payload is overridden by ids parameter", async () => {
    const store = makeStore();
    await store.insert(
      [[0.1, 0.2, 0.3]],
      ["correct-id"],
      [{ id: "wrong-id", data: "test" }],
    );
    const call = mockWrite.mock.calls[0][0];
    expect(call.upsert_rows[0].id).toBe("correct-id");
  });
});

describe("TurbopufferDB search", () => {
  it("queries with correct rank_by, top_k, include_attributes", async () => {
    mockQuery.mockResolvedValue({ rows: [] });
    const store = makeStore();
    await store.search([0.1, 0.2, 0.3], 10);
    expect(mockQuery).toHaveBeenCalledWith({
      rank_by: ["vector", "ANN", [0.1, 0.2, 0.3]],
      top_k: 10,
      include_attributes: true,
    });
  });

  it("defaults top_k to 5", async () => {
    mockQuery.mockResolvedValue({ rows: [] });
    const store = makeStore();
    await store.search([0.1, 0.2, 0.3]);
    expect(mockQuery.mock.calls[0][0].top_k).toBe(5);
  });

  it("maps $dist to score as 1 - $dist and strips $dist and vector", async () => {
    mockQuery.mockResolvedValue({
      rows: [{ id: "r1", $dist: 0.3, vector: [1, 2, 3], data: "payload-val" }],
    });
    const store = makeStore();
    const results = await store.search([0.1, 0.2, 0.3], 5);
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe("r1");
    expect(results[0].score).toBeCloseTo(0.7);
    expect(results[0].payload).toEqual({ data: "payload-val" });
    expect(results[0].payload).not.toHaveProperty("$dist");
    expect(results[0].payload).not.toHaveProperty("vector");
  });

  it("passes single-key filter as bare condition", async () => {
    mockQuery.mockResolvedValue({ rows: [] });
    const store = makeStore();
    await store.search([0.1, 0.2, 0.3], 5, { user_id: "u1" });
    const call = mockQuery.mock.calls[0][0];
    expect(call.filters).toEqual(["user_id", "Eq", "u1"]);
  });

  it("passes multi-key filter as ['And', [...]]", async () => {
    mockQuery.mockResolvedValue({ rows: [] });
    const store = makeStore();
    await store.search([0.1, 0.2, 0.3], 5, { user_id: "u1", agent_id: "a1" });
    const call = mockQuery.mock.calls[0][0];
    expect(call.filters[0]).toBe("And");
    expect(call.filters[1]).toContainEqual(["user_id", "Eq", "u1"]);
    expect(call.filters[1]).toContainEqual(["agent_id", "Eq", "a1"]);
  });

  it("omits filters key when no filters provided", async () => {
    mockQuery.mockResolvedValue({ rows: [] });
    const store = makeStore();
    await store.search([0.1, 0.2, 0.3]);
    const call = mockQuery.mock.calls[0][0];
    expect(call).not.toHaveProperty("filters");
  });

  it("returns [] on query error", async () => {
    mockQuery.mockRejectedValue(new Error("query failed"));
    const store = makeStore();
    const results = await store.search([0.1, 0.2, 0.3]);
    expect(results).toEqual([]);
  });
});

describe("TurbopufferDB get", () => {
  it("queries with id filter and id-based rank, returns first row", async () => {
    mockQuery.mockResolvedValue({
      rows: [{ id: "v1", $dist: 0.1, data: "stuff" }],
    });
    const store = makeStore();
    const result = await store.get("v1");
    expect(result).not.toBeNull();
    expect(result!.id).toBe("v1");
    expect(result!.payload).toEqual({ data: "stuff" });
    const call = mockQuery.mock.calls[0][0];
    expect(call.filters).toEqual(["id", "Eq", "v1"]);
    expect(call.rank_by).toEqual(["id", "asc"]);
  });

  it("returns null when rows are empty", async () => {
    mockQuery.mockResolvedValue({ rows: [] });
    const store = makeStore();
    expect(await store.get("missing")).toBeNull();
  });

  it("returns null on query error", async () => {
    mockQuery.mockRejectedValue(new Error("network error"));
    const store = makeStore();
    expect(await store.get("v1")).toBeNull();
  });
});

describe("TurbopufferDB update", () => {
  it("uses upsert_rows when vector is provided", async () => {
    const store = makeStore();
    await store.update("id-1", [0.1, 0.2, 0.3], { data: "updated" });
    expect(mockWrite).toHaveBeenCalledWith({
      upsert_rows: [{ data: "updated", id: "id-1", vector: [0.1, 0.2, 0.3] }],
      distance_metric: "cosine_distance",
    });
  });

  it("uses patch_rows when vector is empty", async () => {
    const store = makeStore();
    await store.update("id-1", [], { data: "patched" });
    expect(mockWrite).toHaveBeenCalledWith({
      patch_rows: [{ data: "patched", id: "id-1" }],
    });
  });

  it("uses patch_rows when vector is null", async () => {
    const store = makeStore();
    await store.update("id-1", null as any, { data: "patched" });
    expect(mockWrite).toHaveBeenCalledWith({
      patch_rows: [{ data: "patched", id: "id-1" }],
    });
  });
});

describe("TurbopufferDB delete", () => {
  it("calls write with deletes array", async () => {
    const store = makeStore();
    await store.delete("id-1");
    expect(mockWrite).toHaveBeenCalledWith({ deletes: ["id-1"] });
  });
});

describe("TurbopufferDB deleteCol", () => {
  it("calls deleteAll on the namespace", async () => {
    const store = makeStore();
    await store.deleteCol();
    expect(mockDeleteAll).toHaveBeenCalledTimes(1);
  });
});

describe("TurbopufferDB list", () => {
  it("queries with zero vector and returns [rows, count]", async () => {
    mockQuery.mockResolvedValue({
      rows: [
        { id: "r1", $dist: 0.2, val: "a" },
        { id: "r2", $dist: 0.4, val: "b" },
      ],
    });
    const store = makeStore();
    const [rows, count] = await store.list();
    expect(count).toBe(2);
    expect(rows).toHaveLength(2);
    expect(rows[0].id).toBe("r1");
    const call = mockQuery.mock.calls[0][0];
    expect(call.rank_by).toEqual(["id", "asc"]);
    expect(call.top_k).toBe(100);
  });

  it("applies filters when provided", async () => {
    mockQuery.mockResolvedValue({ rows: [{ id: "r1", $dist: 0.1 }] });
    const store = makeStore();
    await store.list({ user_id: "u1" });
    const call = mockQuery.mock.calls[0][0];
    expect(call.filters).toEqual(["user_id", "Eq", "u1"]);
  });

  it("returns [[], 0] on error", async () => {
    mockQuery.mockRejectedValue(new Error("list failed"));
    const store = makeStore();
    const result = await store.list();
    expect(result).toEqual([[], 0]);
  });
});

describe("TurbopufferDB getUserId", () => {
  it("generates a random ID and stores it when namespace is empty", async () => {
    mockMigrationsNs.query.mockResolvedValue({ rows: [] });
    const store = makeStore();
    const id = await store.getUserId();
    expect(typeof id).toBe("string");
    expect(id.length).toBeGreaterThan(0);
    expect(mockMigrationsNs.write).toHaveBeenCalledWith(
      expect.objectContaining({
        upsert_rows: [expect.objectContaining({ id: "1", user_id: id })],
      }),
    );
  });

  it("returns existing user_id without writing when found", async () => {
    mockMigrationsNs.query.mockResolvedValue({
      rows: [{ id: "1", user_id: "existing-user" }],
    });
    const store = makeStore();
    const id = await store.getUserId();
    expect(id).toBe("existing-user");
    expect(mockMigrationsNs.write).not.toHaveBeenCalled();
  });

  it("rethrows on error", async () => {
    mockMigrationsNs.query.mockRejectedValue(new Error("migrations error"));
    const store = makeStore();
    await expect(store.getUserId()).rejects.toThrow("migrations error");
  });
});

describe("TurbopufferDB setUserId", () => {
  it("writes upsert to migrations namespace", async () => {
    const store = makeStore();
    await store.setUserId("my-user-id");
    expect(mockMigrationsNs.write).toHaveBeenCalledWith({
      upsert_rows: [{ id: "1", vector: [0.0], user_id: "my-user-id" }],
      distance_metric: "cosine_distance",
    });
  });

  it("rethrows on error", async () => {
    mockMigrationsNs.write.mockRejectedValue(new Error("write failed"));
    const store = makeStore();
    await expect(store.setUserId("u")).rejects.toThrow("write failed");
  });
});

describe("TurbopufferDB filter conversion", () => {
  it("converts single Eq filter to bare condition", async () => {
    mockQuery.mockResolvedValue({ rows: [] });
    const store = makeStore();
    await store.search([0, 0, 0], 5, { status: "active" });
    const call = mockQuery.mock.calls[0][0];
    expect(call.filters).toEqual(["status", "Eq", "active"]);
  });

  it("converts multi-field filters to ['And', [...]]", async () => {
    mockQuery.mockResolvedValue({ rows: [] });
    const store = makeStore();
    await store.search([0, 0, 0], 5, { user_id: "u1", type: "fact" });
    const call = mockQuery.mock.calls[0][0];
    expect(call.filters[0]).toBe("And");
    expect(call.filters[1]).toHaveLength(2);
  });

  it("converts range filter with gte/lte to multiple conditions", async () => {
    mockQuery.mockResolvedValue({ rows: [] });
    const store = makeStore();
    await store.search([0, 0, 0], 5, { score: { gte: 0.5, lte: 1.0 } } as any);
    const call = mockQuery.mock.calls[0][0];
    // Two conditions wrapped in And
    expect(call.filters[0]).toBe("And");
    expect(call.filters[1]).toContainEqual(["score", "Gte", 0.5]);
    expect(call.filters[1]).toContainEqual(["score", "Lte", 1.0]);
  });

  it("omits filters key when filters object is empty", async () => {
    mockQuery.mockResolvedValue({ rows: [] });
    const store = makeStore();
    await store.search([0, 0, 0], 5, {});
    const call = mockQuery.mock.calls[0][0];
    expect(call).not.toHaveProperty("filters");
  });
});
