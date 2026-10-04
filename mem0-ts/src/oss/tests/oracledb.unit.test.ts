/// <reference types="jest" />
/** Oracle AI Vector Search filter, config and SQL tests. The driver is mocked, so no database is needed. */
const DB_TYPE_VECTOR = { name: "DB_TYPE_VECTOR" };
const DB_TYPE_JSON = { name: "DB_TYPE_JSON" };
const DB_TYPE_VARCHAR = { name: "DB_TYPE_VARCHAR" };

const mockCreatePool = jest.fn();

jest.mock(
  "oracledb",
  () => ({
    thin: true,
    DB_TYPE_VECTOR,
    DB_TYPE_JSON,
    DB_TYPE_VARCHAR,
    createPool: mockCreatePool,
  }),
  { virtual: true },
);

import {
  OracleAIVectorSearch,
  buildWhereClause,
  quoteIdentifier,
} from "../src/vector_stores/oracledb";

type Call = { sql: string; binds: any; options?: any };

function fakeConnection(calls: Call[], resultsBySql: Array<any[][]>) {
  let selectIndex = 0;
  return {
    oracleServerVersionString: "23.4.0.24.05",
    async execute(sql: string, binds: any = {}) {
      calls.push({ sql: sql.replace(/\s+/g, " ").trim(), binds });
      if (/^\s*SELECT/i.test(sql)) {
        return { rows: resultsBySql[selectIndex++] ?? [] };
      }
      return { rows: [] };
    },
    async executeMany(sql: string, binds: any[], options: any = {}) {
      calls.push({ sql: sql.replace(/\s+/g, " ").trim(), binds, options });
      return { rows: [] };
    },
    async commit() {},
    async rollback() {},
    async close() {},
  };
}

function makeStore(
  calls: Call[],
  results: Array<any[][]> = [],
  overrides = {},
) {
  return new OracleAIVectorSearch({
    client: fakeConnection(calls, results) as any,
    collectionName: "mem0",
    embeddingModelDims: 3,
    ...overrides,
  } as any);
}

describe("quoteIdentifier", () => {
  it("quotes a bare name", () => {
    expect(quoteIdentifier("mem0")).toBe('"mem0"');
  });

  it("quotes each segment of a schema-qualified name", () => {
    expect(quoteIdentifier("app.mem0")).toBe('"app"."mem0"');
  });

  it("preserves already-quoted segments", () => {
    expect(quoteIdentifier('"App"."Mem0"')).toBe('"App"."Mem0"');
  });

  it("rejects a name that would break out of the quoting", () => {
    expect(() => quoteIdentifier('mem0" (x); DROP TABLE t--')).toThrow(
      /is not valid/,
    );
  });
});

describe("buildWhereClause", () => {
  it("returns no clause for empty filters", () => {
    expect(buildWhereClause(undefined)).toEqual(["", {}]);
    expect(buildWhereClause({})).toEqual(["", {}]);
  });

  it("binds a scalar equality instead of inlining it", () => {
    const [clause, binds] = buildWhereClause({ user_id: "alice" });
    expect(clause).toBe(
      `WHERE JSON_EXISTS(payload, '$."user_id"?(@ == $f_0)' PASSING :f_0 AS "f_0")`,
    );
    expect(binds).toEqual({ f_0: "alice" });
  });

  it("ANDs multiple fields", () => {
    const [clause, binds] = buildWhereClause({
      user_id: "alice",
      agent_id: "bot",
    });
    expect(clause.startsWith("WHERE (")).toBe(true);
    expect(clause).toContain(" AND ");
    expect(binds).toEqual({ f_0: "alice", f_1: "bot" });
  });

  it("applies every operator in a compound range filter", () => {
    const [clause, binds] = buildWhereClause({ age: { gte: 10, lte: 20 } });
    expect(clause).toContain("@ >= $f_0 && @ <= $f_1");
    expect(binds).toEqual({ f_0: 10, f_1: 20 });
  });

  it("builds an existence check for the wildcard filter", () => {
    const [clause, binds] = buildWhereClause({ user_id: "*" });
    expect(clause).toBe(`WHERE JSON_EXISTS(payload, '$."user_id"')`);
    expect(binds).toEqual({});
  });

  it("builds membership for in and negates it for nin", () => {
    const [inClause] = buildWhereClause({ user_id: { in: ["a", "b"] } });
    expect(inClause).toContain("@ in ($f_0, $f_1)");
    expect(inClause).not.toContain("NOT (");

    const [ninClause] = buildWhereClause({ user_id: { nin: ["a"] } });
    expect(ninClause).toContain("NOT (");
  });

  it("lowercases the operand for icontains", () => {
    const [clause, binds] = buildWhereClause({ data: { icontains: "SciFi" } });
    expect(clause).toContain("@.lower() has substring $f_0");
    expect(binds).toEqual({ f_0: "scifi" });
  });

  it("ORs the branches of a $or group", () => {
    const [clause, binds] = buildWhereClause({
      $or: [{ user_id: "alice" }, { agent_id: "bot" }],
    });
    expect(clause).toContain(" OR ");
    expect(binds).toEqual({ f_0: "alice", f_1: "bot" });
  });

  it("negates a $not group", () => {
    const [clause] = buildWhereClause({ $not: [{ user_id: "alice" }] });
    expect(clause.startsWith("WHERE NOT (")).toBe(true);
  });

  it("nests logical groups", () => {
    const [clause, binds] = buildWhereClause({
      user_id: "alice",
      $or: [{ agent_id: "bot" }, { run_id: "r1" }],
    });
    expect(clause).toContain(" AND ");
    expect(clause).toContain(" OR ");
    expect(Object.keys(binds)).toEqual(["f_0", "f_1", "f_2"]);
  });

  it("compares against JSON null without a bind", () => {
    const [clause, binds] = buildWhereClause({ agent_id: null });
    expect(clause).toBe(
      `WHERE JSON_EXISTS(payload, '$."agent_id"?(@ == null)')`,
    );
    expect(binds).toEqual({});
  });

  it("rejects a metadata key that could escape the JSON path", () => {
    expect(() => buildWhereClause({ 'a"?(1==1))--': "x" })).toThrow(
      /Invalid metadata key/,
    );
  });

  it("rejects an unsupported field operator", () => {
    expect(() => buildWhereClause({ age: { regex: "^a" } })).toThrow(
      /Unsupported Oracle filter operator/,
    );
  });

  it("rejects an unsupported logical operator", () => {
    expect(() => buildWhereClause({ $nor: [{ a: 1 }] })).toThrow(
      /Unsupported Oracle logical filter operator/,
    );
  });

  it("rejects an empty in list", () => {
    expect(() => buildWhereClause({ user_id: { in: [] } })).toThrow(
      /non-empty array/,
    );
  });

  it("rejects a non-scalar comparison operand", () => {
    expect(() => buildWhereClause({ age: { gt: [1] } })).toThrow(
      /requires a scalar value/,
    );
  });
});

describe("OracleAIVectorSearch config validation", () => {
  it("requires connectionParams or client", () => {
    expect(() => new OracleAIVectorSearch({} as any)).toThrow(
      /connectionParams.*client/,
    );
  });

  it("rejects an unsupported distance metric", () => {
    expect(() => makeStore([], [], { distanceMetric: "JACCARD" })).toThrow(
      /Unsupported distance metric/,
    );
  });

  it("rejects a non-positive embedding dimension", () => {
    expect(() => makeStore([], [], { embeddingModelDims: 0 })).toThrow(
      /positive integer/,
    );
  });

  it("rejects an out-of-range index accuracy", () => {
    expect(() => makeStore([], [], { indexAccuracy: 101 })).toThrow(
      /between 1 and 100/,
    );
  });

  it("rejects an index parameter that does not belong to the index type", () => {
    expect(() =>
      makeStore([], [], {
        indexType: "HNSW",
        indexParameters: { samples_per_partition: 10 },
      }),
    ).toThrow(/Unsupported HNSW index parameter/);
  });

  it("rejects an index parameter outside its allowed range", () => {
    expect(() =>
      makeStore([], [], { indexParameters: { neighbors: 1 } }),
    ).toThrow(/between 2 and 2048/);
  });
});

describe("OracleAIVectorSearch SQL", () => {
  it("creates the table and a vector index on initialize", async () => {
    const calls: Call[] = [];
    await makeStore(calls, [], {
      indexParameters: { neighbors: 32, efconstruction: 200 },
      indexAccuracy: 95,
    }).initialize();

    const ddl = calls.map((c) => c.sql).join("\n");
    expect(ddl).toContain(
      'CREATE TABLE IF NOT EXISTS "mem0" ( id VARCHAR2(36) PRIMARY KEY, vector VECTOR(3), payload JSON )',
    );
    expect(ddl).toContain(
      'CREATE VECTOR INDEX IF NOT EXISTS "mem0_VEC_IDX" ON "mem0" (vector) ORGANIZATION INMEMORY NEIGHBOR GRAPH DISTANCE COSINE WITH TARGET ACCURACY 95 PARAMETERS (type HNSW, neighbors 32, efconstruction 200)',
    );
  });

  it("skips index creation when doCreateIndex is false", async () => {
    const calls: Call[] = [];
    await makeStore(calls, [], { doCreateIndex: false }).initialize();
    expect(calls.map((c) => c.sql).join("\n")).not.toContain(
      "CREATE VECTOR INDEX",
    );
  });

  it("binds vectors as DB_TYPE_VECTOR and payloads as DB_TYPE_JSON on insert", async () => {
    const calls: Call[] = [];
    await makeStore(calls).insert([[1, 2, 3]], ["id-1"], [{ data: "hello" }]);

    const insert = calls.find((c) => c.sql.startsWith("INSERT INTO"))!;
    expect(insert.binds).toEqual([
      {
        id: "id-1",
        vector: new Float32Array([1, 2, 3]),
        payload: { data: "hello" },
      },
    ]);
    expect(insert.options.bindDefs.id).toEqual({
      type: DB_TYPE_VARCHAR,
      maxSize: 36,
    });
    expect(insert.options.bindDefs.vector.type).toBe(DB_TYPE_VECTOR);
    expect(insert.options.bindDefs.payload.type).toBe(DB_TYPE_JSON);
  });

  it("issues a single executeMany call with one bind row per vector on a multi-row insert", async () => {
    const calls: Call[] = [];
    await makeStore(calls).insert(
      [
        [1, 2, 3],
        [4, 5, 6],
      ],
      ["id-1", "id-2"],
      [{ a: 1 }, { b: 2 }],
    );

    const inserts = calls.filter((c) => c.sql.startsWith("INSERT INTO"));
    expect(inserts).toHaveLength(1);
    expect(inserts[0].binds).toHaveLength(2);
    expect(inserts[0].binds[0].id).toBe("id-1");
    expect(inserts[0].binds[1].id).toBe("id-2");
  });

  it("issues no insert statement when inserting an empty batch", async () => {
    const calls: Call[] = [];
    await makeStore(calls).insert([], [], []);
    expect(calls.filter((c) => c.sql.startsWith("INSERT INTO"))).toHaveLength(
      0,
    );
  });

  it("rejects insert batches whose IDs or payloads do not match vectors", async () => {
    const store = makeStore([]);

    await expect(store.insert([[1, 2, 3]], [], [{}])).rejects.toThrow(
      "ids and vectors must have the same length",
    );
    await expect(store.insert([[1, 2, 3]], ["id-1"], [])).rejects.toThrow(
      "payloads and vectors must have the same length",
    );
  });

  it("converts cosine distance to a similarity score", async () => {
    const calls: Call[] = [];
    const store = makeStore(calls, [[["id-1", { data: "hello" }, 0.25]]]);
    const results = await store.search([1, 2, 3], 5);

    expect(results).toEqual([
      { id: "id-1", payload: { data: "hello" }, score: 0.75 },
    ]);
    const select = calls.find((c) => c.sql.includes("VECTOR_DISTANCE"))!;
    expect(select.sql).toContain(
      "VECTOR_DISTANCE(vector, :query_vec, COSINE) distance",
    );
    expect(select.sql).toContain("FETCH APPROX FIRST :max_rows ROWS ONLY");
    expect(select.binds.max_rows).toBe(5);
  });

  it("inverts the sign of a DOT distance", async () => {
    const store = makeStore([], [[["id-1", {}, -0.4]]], {
      distanceMetric: "DOT",
    });
    const [result] = await store.search([1, 2, 3]);
    expect(result.score).toBeCloseTo(0.4);
  });

  it("adds the VECTOR_INDEX_TRANSFORM hint when searching without filters", async () => {
    const calls: Call[] = [];
    const store = makeStore(calls, [[["id-1", {}, 0.1]]]);
    await store.search([1, 2, 3], 5);

    const select = calls.find((c) => c.sql.includes("VECTOR_DISTANCE"))!;
    expect(select.sql).toContain('/*+ VECTOR_INDEX_TRANSFORM("mem0") */');
  });

  it("omits the VECTOR_INDEX_TRANSFORM hint when searching with filters", async () => {
    const calls: Call[] = [];
    const store = makeStore(calls, [[["id-1", {}, 0.1]]]);
    await store.search([1, 2, 3], 5, { user_id: "alice" });

    const select = calls.find((c) => c.sql.includes("VECTOR_DISTANCE"))!;
    expect(select.sql).not.toContain("VECTOR_INDEX_TRANSFORM");
  });

  it("parses a payload returned as a JSON string", async () => {
    const store = makeStore([], [[["id-1", '{"data":"hello"}']]]);
    expect(await store.get("id-1")).toEqual({
      id: "id-1",
      payload: { data: "hello" },
    });
  });

  it("returns null when get finds no row", async () => {
    expect(await makeStore([], [[]]).get("missing")).toBeNull();
  });

  it("generates and persists a UUID user id when none is stored", async () => {
    const calls: Call[] = [];
    const userId = await makeStore(calls, [[]]).getUserId();

    expect(userId).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
    const insert = calls.find((c) =>
      c.sql.startsWith("INSERT INTO memory_migrations"),
    )!;
    expect(insert.binds).toEqual({ user_id: userId });
  });

  it("returns the stored user id when one exists", async () => {
    expect(await makeStore([], [[["alice"]]]).getUserId()).toBe("alice");
  });

  it("returns rows and the total count from list", async () => {
    const calls: Call[] = [];
    const store = makeStore(calls, [[["id-1", { data: "hello" }, 7]]]);
    const [results, count] = await store.list({ user_id: "alice" }, 10);

    expect(results).toEqual([{ id: "id-1", payload: { data: "hello" } }]);
    expect(count).toBe(7);

    const selects = calls.filter((c) => /^SELECT/i.test(c.sql));
    expect(selects).toHaveLength(1);
    const [list] = selects;
    expect(list.sql).toContain(
      "SELECT id, payload, COUNT(*) OVER () total FROM",
    );
    expect(list.sql).toContain("WHERE JSON_EXISTS(payload,");
    expect(list.binds).toEqual({ f_0: "alice", max_rows: 10 });
  });

  it("returns a total of 0 from list when no rows match", async () => {
    const store = makeStore([], [[]]);
    const [results, count] = await store.list();
    expect(results).toEqual([]);
    expect(count).toBe(0);
  });
});

describe("OracleAIVectorSearch initialization failure", () => {
  beforeEach(() => mockCreatePool.mockReset());

  function fakePool(serverVersion: string) {
    const connection = {
      ...fakeConnection([], []),
      oracleServerVersionString: serverVersion,
    };
    return {
      close: jest.fn(async () => {}),
      getConnection: jest.fn(async () => connection),
    };
  }

  function makePoolStore() {
    return new OracleAIVectorSearch({
      connectionParams: { user: "u", password: "p", connectString: "d" },
      collectionName: "mem0",
      embeddingModelDims: 3,
    } as any);
  }

  it("closes the pool it owns when initialization fails", async () => {
    const pool = fakePool("23.3.0.24.05");
    mockCreatePool.mockResolvedValue(pool);

    await expect(makePoolStore().initialize()).rejects.toThrow(
      "Oracle DB version 23.3.0.24.05 not supported",
    );
    expect(pool.close).toHaveBeenCalledTimes(1);
  });

  it("does not cache the rejection, so a later attempt can succeed", async () => {
    const failing = fakePool("23.3.0.24.05");
    const working = fakePool("23.4.0.24.05");
    mockCreatePool
      .mockResolvedValueOnce(failing)
      .mockResolvedValueOnce(working);

    const store = makePoolStore();
    await expect(store.initialize()).rejects.toThrow("not supported");
    await expect(store.initialize()).resolves.toBeUndefined();
    expect(mockCreatePool).toHaveBeenCalledTimes(2);
  });

  it("leaves a caller-supplied client open when initialization fails", async () => {
    const client = fakeConnection([], []);
    client.oracleServerVersionString = "23.3.0.24.05";
    const close = jest.spyOn(client, "close");

    const store = new OracleAIVectorSearch({
      client: client as any,
      collectionName: "mem0",
      embeddingModelDims: 3,
    } as any);

    await expect(store.initialize()).rejects.toThrow("not supported");
    expect(close).not.toHaveBeenCalled();
  });
});
