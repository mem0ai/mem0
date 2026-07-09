import {
  AutoBuildPolicyType,
  FieldType,
  IndexType,
  InvertedIndexFieldAttribute,
  MetricType,
  PartitionType,
  ServerErrCode,
  TableState,
} from "@mochow/mochow-sdk-node";
import { BaiduDB } from "../src/vector_stores/baidu";

// No jest.mock() here on purpose: the real SDK supplies the enums and the search request
// classes (which carry an internal `set` map the client reads, so they cannot be hand-rolled
// as plain literals). Only the network-facing MochowClient is faked, via the `client` config.

const OK = { code: 0, msg: "" };
const DIMS = 1536;

const normalTable = (schema: unknown = { fields: [], indexes: [] }) => ({
  ...OK,
  table: { state: TableState.Normal, schema },
});

const CORE_FIELDS = [
  { fieldName: "id", fieldType: FieldType.String },
  { fieldName: "data", fieldType: FieldType.Text },
  { fieldName: "vector", fieldType: FieldType.FloatVector, dimension: DIMS },
  { fieldName: "metadata", fieldType: "JSON" },
];

const BM25_FIELDS = [
  ...CORE_FIELDS,
  { fieldName: "textLemmatized", fieldType: FieldType.Text },
];

/** Records call order, so ordering regressions (deleteCol vs. in-flight init) are visible. */
function fakeClient(overrides: Record<string, (...args: any[]) => any> = {}) {
  const calls: string[] = [];
  const track =
    (name: string, impl: (...args: any[]) => any) =>
    (...args: any[]) => {
      calls.push(name);
      return impl(...args);
    };

  const client: any = {
    calls,
    createDatabase: jest.fn(track("createDatabase", async () => OK)),
    createTable: jest.fn(track("createTable", async () => OK)),
    dropTable: jest.fn(track("dropTable", async () => OK)),
    descTable: jest.fn(track("descTable", async () => normalTable())),
    upsert: jest.fn(async () => OK),
    delete: jest.fn(async () => OK),
    query: jest.fn(),
    select: jest.fn(),
    vectorSearch: jest.fn(),
    bm25Search: jest.fn(),
  };

  for (const [name, impl] of Object.entries(overrides)) {
    client[name] = jest.fn(track(name, impl));
  }
  return client;
}

const makeStore = (client: any, extra: Record<string, unknown> = {}) =>
  new BaiduDB({
    endpoint: "http://127.0.0.1:5287",
    account: "root",
    apiKey: "test-key",
    databaseName: "mem0_db",
    tableName: "mem0",
    embeddingModelDims: DIMS,
    client,
    ...extra,
  } as any);

/** Run the poll loop's setTimeout inline so tests never wait the real 2s interval. */
const runTimersInline = () =>
  jest.spyOn(global, "setTimeout").mockImplementation(((fn: () => void) => {
    fn();
    return 0;
  }) as any);

beforeEach(() => {
  jest.spyOn(console, "warn").mockImplementation(() => {});
  jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => jest.restoreAllMocks());

describe("BaiduDB config", () => {
  it("rejects a missing required field", () => {
    expect(() => makeStore(fakeClient(), { tableName: "" })).toThrow(
      /non-empty 'tableName'/,
    );
  });

  it("does not require endpoint credentials when a client is injected", () => {
    expect(() =>
      makeStore(fakeClient(), { endpoint: "", account: "", apiKey: "" }),
    ).not.toThrow();
  });
});

describe("BaiduDB table provisioning", () => {
  it("creates the table with the schema mem0 needs", async () => {
    const client = fakeClient();
    await makeStore(client).initialize();

    const spec = client.createTable.mock.calls[0][0];
    expect(client.createDatabase).toHaveBeenCalledWith("mem0_db");
    expect(spec.database).toBe("mem0_db");
    expect(spec.table).toBe("mem0");
    expect(spec.enableDynamicField).toBe(false);
    // Mochow rejects a partition without partitionType.
    expect(spec.partition).toEqual({
      partitionType: PartitionType.HASH,
      partitionNum: 1,
    });

    const fields = spec.schema.fields.map((f: any) => [
      f.fieldName,
      f.fieldType,
    ]);
    expect(fields).toEqual([
      ["id", FieldType.String],
      ["data", FieldType.Text],
      ["vector", FieldType.FloatVector],
      ["textLemmatized", FieldType.Text],
      ["metadata", "JSON"],
    ]);
    expect(spec.schema.fields[0]).toMatchObject({
      primaryKey: true,
      partitionKey: true,
      notNull: true,
    });
    expect(spec.schema.fields[2].dimension).toBe(DIMS);
  });

  it("builds a vector index with a genuine row-count-increment auto-build policy", async () => {
    const client = fakeClient();
    await makeStore(client).initialize();

    const [vectorIndex] = client.createTable.mock.calls[0][0].schema.indexes;
    expect(vectorIndex).toMatchObject({
      indexName: "vector_idx",
      indexType: IndexType.HNSW,
      field: "vector",
      metricType: MetricType.L2,
      params: { M: 16, efConstruction: 200 },
      autoBuild: true,
    });
    // Regression guard: sdk.AutoBuildIncrement() stamps policyType "TIMING" in 2.1.5.
    expect(vectorIndex.autoBuildPolicy).toEqual({
      policyType: AutoBuildPolicyType.Increment,
      rowCountIncrement: 10000,
    });
    expect(AutoBuildPolicyType.Increment).not.toBe(AutoBuildPolicyType.Timing);
  });

  it("declares the filtering and BM25 indexes with an indexType", async () => {
    const client = fakeClient();
    await makeStore(client).initialize();

    const [, filtering, bm25] =
      client.createTable.mock.calls[0][0].schema.indexes;
    expect(filtering).toEqual({
      indexName: "metadata_filtering_idx",
      indexType: IndexType.FilteringIndex,
      fields: ["metadata"],
    });
    // Memory.search() hands keywordSearch() an already-lemmatized query, so raw `data` is
    // not worth indexing — only the lemmatized column is. The index is therefore named for
    // that column and must never be called "data_bm25_idx": that is the name Python's
    // keyword_search() queries with a raw, unstemmed query, and it must keep missing (and so
    // falling back to vector search) rather than half-matching this stemmed index.
    expect(bm25).toMatchObject({
      indexName: "text_lemmatized_bm25_idx",
      indexType: IndexType.InvertedIndex,
      fields: ["textLemmatized"],
      fieldAttributes: [InvertedIndexFieldAttribute.Analyzed],
    });
  });

  it("honours a configured metric type", async () => {
    const client = fakeClient();
    await makeStore(client, { metricType: "COSINE" }).initialize();
    const [vectorIndex] = client.createTable.mock.calls[0][0].schema.indexes;
    expect(vectorIndex.metricType).toBe(MetricType.COSINE);
  });

  it("tolerates an existing database and table", async () => {
    const client = fakeClient({
      createDatabase: async () => ({
        code: ServerErrCode.DBAlreadyExist,
        msg: "db exists",
      }),
      createTable: async () => ({
        code: ServerErrCode.TableAlreadyExist,
        msg: "table exists",
      }),
      descTable: async () => normalTable({ fields: BM25_FIELDS, indexes: [] }),
    });
    await expect(makeStore(client).initialize()).resolves.toBeUndefined();
  });

  it("waits for a CREATING table to become NORMAL", async () => {
    runTimersInline();
    const states = [
      TableState.Creating,
      TableState.Creating,
      TableState.Normal,
    ];
    const client = fakeClient({
      descTable: async () => ({
        ...OK,
        table: { state: states.shift(), schema: { fields: [], indexes: [] } },
      }),
    });

    await makeStore(client).initialize();
    expect(client.descTable).toHaveBeenCalledTimes(3);
  });

  it("surfaces a non-zero envelope as an error rather than succeeding", async () => {
    const client = fakeClient({
      createTable: async () => ({
        code: ServerErrCode.InvalidTableSchema,
        msg: "bad schema",
      }),
    });
    await expect(makeStore(client).initialize()).rejects.toThrow(
      /createTable 'mem0' failed \(code 60\): bad schema/,
    );
  });

  it("rejects an existing table whose vector dimension disagrees", async () => {
    const client = fakeClient({
      createTable: async () => ({
        code: ServerErrCode.TableAlreadyExist,
        msg: "",
      }),
      descTable: async () =>
        normalTable({
          fields: [
            CORE_FIELDS[0],
            CORE_FIELDS[1],
            {
              fieldName: "vector",
              fieldType: FieldType.FloatVector,
              dimension: 768,
            },
            CORE_FIELDS[3],
          ],
          indexes: [],
        }),
    });
    await expect(makeStore(client).initialize()).rejects.toThrow(
      /stores 768-dimensional vectors, but 'embeddingModelDims' is 1536/,
    );
  });

  it("rejects an existing table missing the core schema", async () => {
    const client = fakeClient({
      createTable: async () => ({
        code: ServerErrCode.TableAlreadyExist,
        msg: "",
      }),
      descTable: async () =>
        normalTable({ fields: [CORE_FIELDS[0]], indexes: [] }),
    });
    await expect(makeStore(client).initialize()).rejects.toThrow(
      /missing the id\/data\/vector\/metadata schema/,
    );
  });
});

describe("BaiduDB keyword search support detection", () => {
  it("fails closed when an existing table has no inverted index", async () => {
    const client = fakeClient({
      createTable: async () => ({
        code: ServerErrCode.TableAlreadyExist,
        msg: "",
      }),
      descTable: async () => normalTable({ fields: CORE_FIELDS, indexes: [] }),
    });
    const store = makeStore(client);

    await expect(store.keywordSearch("hello")).resolves.toBeNull();
    expect(client.bm25Search).not.toHaveBeenCalled();
    expect(console.warn).toHaveBeenCalledWith(
      expect.stringContaining("text_lemmatized_bm25_idx"),
    );
  });

  it("enables keyword search when the existing table carries the BM25 index", async () => {
    const client = fakeClient({
      createTable: async () => ({
        code: ServerErrCode.TableAlreadyExist,
        msg: "",
      }),
      descTable: async () =>
        normalTable({
          fields: BM25_FIELDS,
          indexes: [{ indexName: "text_lemmatized_bm25_idx" }],
        }),
    });
    client.bm25Search.mockResolvedValue({ ...OK, rows: [] });

    await expect(makeStore(client).keywordSearch("hello")).resolves.toEqual([]);
    expect(client.bm25Search).toHaveBeenCalled();
  });

  it("queries the inverted index with the caller's already-lemmatized text", async () => {
    const client = fakeClient();
    client.bm25Search.mockResolvedValue({
      ...OK,
      rows: [
        { row: { id: "m1", data: "loves pizza", metadata: {} }, score: 3.5 },
      ],
    });

    const results = await makeStore(client).keywordSearch("love pizza", 7, {
      userId: "alice",
    });
    expect(results).toEqual([
      { id: "m1", payload: { data: "loves pizza" }, score: 3.5 },
    ]);

    const { request, ...ns } = client.bm25Search.mock.calls[0][0];
    expect(ns).toEqual({ database: "mem0_db", table: "mem0" });
    expect(request.indexName).toBe("text_lemmatized_bm25_idx");
    expect(request.searchText).toBe("love pizza");
    expect(request.limit).toBe(7);
    expect(request.filter).toBe('metadata["userId"] = "alice"');
  });
});

describe("BaiduDB writes", () => {
  it("upserts the whole batch in one call and mirrors textLemmatized out of the payload", async () => {
    const client = fakeClient();

    await makeStore(client).insert(
      [
        [1, 2],
        [3, 4],
      ],
      ["a", "b"],
      [
        { data: "loves pizza", textLemmatized: "love pizza" },
        { data: "runs daily" },
      ],
    );

    expect(client.upsert).toHaveBeenCalledTimes(1);
    expect(client.upsert.mock.calls[0][0]).toEqual({
      database: "mem0_db",
      table: "mem0",
      rows: [
        {
          id: "a",
          data: "loves pizza",
          vector: [1, 2],
          textLemmatized: "love pizza",
          metadata: {},
        },
        // Falls back to `data` when the caller did not lemmatize.
        {
          id: "b",
          data: "runs daily",
          vector: [3, 4],
          textLemmatized: "runs daily",
          metadata: {},
        },
      ],
    });
  });

  it("refuses a ragged batch instead of silently truncating it", async () => {
    await expect(
      makeStore(fakeClient()).insert([[1]], ["a", "b"], [{}]),
    ).rejects.toThrow(/equal length \(got 1\/2\/1\)/);
  });

  it("updates and deletes by primary key", async () => {
    const client = fakeClient();
    const store = makeStore(client);

    await store.update("m1", [9], { data: "new" });
    expect(client.upsert.mock.calls[0][0].rows).toEqual([
      {
        id: "m1",
        data: "new",
        vector: [9],
        textLemmatized: "new",
        metadata: {},
      },
    ]);

    await store.delete("m1");
    expect(client.delete).toHaveBeenCalledWith({
      database: "mem0_db",
      table: "mem0",
      primaryKey: { id: "m1" },
    });
  });

  it("throws when the server rejects an upsert", async () => {
    const client = fakeClient();
    client.upsert.mockResolvedValue({ code: 100, msg: "duplicate key" });

    await expect(makeStore(client).insert([[1]], ["a"], [{}])).rejects.toThrow(
      /upsert failed \(code 100\): duplicate key/,
    );
  });
});

describe("BaiduDB reads", () => {
  it("maps vector search hits out of the nested row envelope", async () => {
    const client = fakeClient();
    client.vectorSearch.mockResolvedValue({
      ...OK,
      rows: [
        {
          row: { id: "m1", data: "x", metadata: {} },
          distance: 0.2,
          score: 0.8,
        },
      ],
    });

    const results = await makeStore(client).search([1, 2, 3], 5, {
      userId: "alice",
    });
    expect(results).toEqual([{ id: "m1", payload: { data: "x" }, score: 0.8 }]);

    const { request } = client.vectorSearch.mock.calls[0][0];
    expect(request.vectorField).toBe("vector");
    expect(request.vector).toEqual({ vector: [1, 2, 3] });
    expect(request.limit).toBe(5);
    expect(request.filter).toBe('metadata["userId"] = "alice"');
    expect(request.projections).toEqual(["id", "data", "metadata"]);
    expect(request.config.params).toEqual({ ef: 200 });
  });

  it("omits the filter when no filters are supplied", async () => {
    const client = fakeClient();
    client.vectorSearch.mockResolvedValue({ ...OK, rows: [] });
    await makeStore(client).search([1], 5);
    expect(client.vectorSearch.mock.calls[0][0].request.filter).toBeUndefined();
  });

  it("escapes quotes and rejects unsafe filter keys and values", async () => {
    const client = fakeClient();
    client.vectorSearch.mockResolvedValue({ ...OK, rows: [] });
    const store = makeStore(client);

    await store.search([1], 5, { userId: 'a"b', runId: 3, agentId: true });
    expect(client.vectorSearch.mock.calls[0][0].request.filter).toBe(
      'metadata["userId"] = "a\\"b" AND metadata["runId"] = 3 AND metadata["agentId"] = true',
    );

    await expect(store.search([1], 5, { "bad key": "x" })).rejects.toThrow(
      /Invalid filter key/,
    );
    await expect(
      store.search([1], 5, { userId: ["a"] as any }),
    ).rejects.toThrow(/must be str, int, float, or bool, got array/);
  });

  it("returns null for a missing id and throws on a real query failure", async () => {
    const client = fakeClient();
    const store = makeStore(client);

    client.query.mockResolvedValue({ ...OK, row: {} });
    await expect(store.get("nope")).resolves.toBeNull();

    client.query.mockResolvedValue({
      ...OK,
      row: { id: "m1", data: "stored text", metadata: { a: 1 } },
    });
    await expect(store.get("m1")).resolves.toEqual({
      id: "m1",
      payload: { a: 1, data: "stored text" },
    });

    client.query.mockResolvedValue({ code: 2, msg: "invalid parameter" });
    await expect(store.get("m1")).rejects.toThrow(
      /query 'm1' failed \(code 2\): invalid parameter/,
    );
  });

  // The server signals a missing primary key with code 101; pymochow and mochow-sdk-go both
  // name it (ROW_KEY_NOT_FOUND / RowKeyNotFound). The Node SDK's ServerErrCode stops at 100,
  // so it has to be spelled out. Memory.get()/update()/delete() all branch on a null here.
  it("returns null when the server reports the row key is missing", async () => {
    const client = fakeClient();
    const store = makeStore(client);

    client.query.mockResolvedValue({ code: 101, msg: "row key not found" });
    await expect(store.get("nope")).resolves.toBeNull();
  });

  it("lists flat select rows and reports how many came back", async () => {
    const client = fakeClient();
    client.select.mockResolvedValue({
      ...OK,
      isTruncated: false,
      nextMarker: "",
      rows: [{ id: "m1", data: "x", metadata: {} }, { id: "m2" }],
    });

    await expect(
      makeStore(client).list({ userId: "alice" }, 50),
    ).resolves.toEqual([
      [
        { id: "m1", payload: { data: "x" } },
        { id: "m2", payload: {} },
      ],
      2,
    ]);
    expect(client.select).toHaveBeenCalledWith({
      database: "mem0_db",
      table: "mem0",
      filter: 'metadata["userId"] = "alice"',
      projections: ["id", "data", "metadata"],
      limit: 50,
    });
  });
});

describe("BaiduDB deleteCol", () => {
  it("waits for the drop to land before returning", async () => {
    runTimersInline();
    const client = fakeClient();
    const store = makeStore(client);
    await store.initialize();

    client.descTable
      .mockResolvedValueOnce({ ...OK, table: { state: TableState.Deleting } })
      .mockResolvedValueOnce({
        code: ServerErrCode.TableNotExist,
        msg: "gone",
      });

    await store.deleteCol();
    expect(client.dropTable).toHaveBeenCalledWith("mem0_db", "mem0");
    expect(client.descTable).toHaveBeenCalledTimes(3); // 1 from initialize + 2 polls
  });

  it("is a no-op when the table is already gone", async () => {
    const client = fakeClient();
    const store = makeStore(client);
    await store.initialize();

    client.dropTable.mockResolvedValue({
      code: ServerErrCode.TableNotExist,
      msg: "gone",
    });
    await expect(store.deleteCol()).resolves.toBeUndefined();
  });

  // Regression: deleteCol() used to run alongside the fire-and-forget initialize() the
  // constructor starts, so the in-flight createTable landed *after* dropTable and the table
  // survived reset().
  it("does not race the initialize() the constructor kicks off", async () => {
    runTimersInline();
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });

    // The table exists after the first init, is gone once dropTable lands, then exists again.
    const descQueue: unknown[] = [
      normalTable(),
      { code: ServerErrCode.TableNotExist, msg: "gone" },
    ];
    const client = fakeClient({
      createDatabase: async () => {
        await gate;
        return OK;
      },
      descTable: async () => descQueue.shift() ?? normalTable(),
    });

    const store = makeStore(client); // initialize() is now in flight, parked on `gate`
    const resetting = store.reset();
    release();
    await resetting;

    expect(client.calls).toEqual([
      "createDatabase",
      "createTable",
      "descTable",
      "dropTable",
      "descTable",
      "createDatabase",
      "createTable",
      "descTable",
    ]);
    expect(client.calls.indexOf("dropTable")).toBeGreaterThan(
      client.calls.indexOf("createTable"),
    );
    expect(client.createTable).toHaveBeenCalledTimes(2);
  });
});

describe("BaiduDB user id", () => {
  it("round-trips the store user id", async () => {
    const store = makeStore(fakeClient());
    await expect(store.getUserId()).resolves.toBe("anonymous-baidu-user");
    await store.setUserId("alice");
    await expect(store.getUserId()).resolves.toBe("alice");
  });
});
